#!/usr/bin/env python3
"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

Data Visualizer for AWS Shopfloor Connectivity (SFC)
Provides ncurses-based visualization for time-series data from SFC.
Cross-platform support for Windows, macOS, and Linux.
"""

import os
import json
import glob
import platform

# Handle cross-platform curses implementation
try:
    import curses
except ImportError:
    if platform.system() == "Windows":
        print("Warning: Standard curses not available on Windows")
        try:
            import windows_curses as curses

            print("Successfully loaded windows-curses")
        except ImportError:
            print(
                "windows-curses package not found. Install with: uv add windows-curses"
            )
            curses = None
    else:
        # Re-raise on non-Windows platforms since curses should be available
        raise
import time
import datetime
import jmespath
import io
import base64
import matplotlib

matplotlib.use("Agg")  # Use non-interactive backend for headless server use
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from typing import List, Dict, Any, Optional, Tuple


class DataVisualizer:
    """
    Ncurses-based data visualizer for time series data from SFC
    """

    def __init__(self):
        self.data_points = []
        self.timestamps = []
        self.min_value = 0
        self.max_value = 0
        self.title = ""

    def _load_data_files(self, data_dir: str) -> List[Dict]:
        """Load data from all JSON files in the directory recursively"""
        all_data = []
        error_count = 0

        # Get a list of all JSON files in the directory and its subdirectories and sort them by name
        json_files = sorted(
            glob.glob(os.path.join(data_dir, "**", "*.json"), recursive=True)
        )

        for file_path in json_files:
            try:
                with open(file_path, "r") as f:
                    file_data = json.load(f)
                    if isinstance(file_data, list):
                        all_data.extend(file_data)
                    else:
                        all_data.append(file_data)
            except Exception:
                error_count += 1

        # Print a single message about errors if any occurred
        if error_count > 0:
            print(f"Could not load {error_count} file(s). Some data may be missing.")

        return all_data

    def _calculate_spline_points(self, x0, y0, x1, y1, x2, y2, x3, y3, num_points=15):
        """Calculate points along a cubic spline for smooth curves"""
        points = []

        # Generate intermediate points using a cubic Catmull-Rom spline
        # This is a simplified version suitable for terminal graphics
        for t in range(num_points + 1):
            t = t / num_points

            # Catmull-Rom basis functions
            h00 = 2 * t**3 - 3 * t**2 + 1
            h10 = t**3 - 2 * t**2 + t
            h01 = -2 * t**3 + 3 * t**2
            h11 = t**3 - t**2

            # Only use the middle segment
            px = h00 * x1 + h10 * (x2 - x0) + h01 * x2 + h11 * (x3 - x1)
            py = h00 * y1 + h10 * (y2 - y0) + h01 * y2 + h11 * (y3 - y1)

            # Keep floating point precision until final rendering
            points.append((px, py))

        return points

    def _extract_values(
        self, data: List[Dict], jmespath_expr: str
    ) -> Tuple[List[float], List[str]]:
        """Extract values and timestamps using the provided JMESPath expression"""
        values = []
        timestamps = []
        error_count = 0

        for item in data:
            try:
                # Extract the value using JMESPath
                value = jmespath.search(jmespath_expr, item)
                if value is not None and isinstance(value, (int, float)):
                    values.append(float(value))

                    # Extract timestamp from the item
                    timestamp = item.get("timestamp", "")
                    timestamps.append(timestamp)
            except Exception:
                error_count += 1

        # Print a single message if errors occurred
        if error_count > 0:
            print(
                f"Failed to extract data from {error_count} item(s) using expression '{jmespath_expr}'."
            )

        return values, timestamps

    def _prepare_data(
        self, data_dir: str, jmespath_expr: str, timeframe_seconds: Optional[int] = None
    ) -> bool:
        """Load and prepare data for visualization"""
        # Load all data files
        all_data = self._load_data_files(data_dir)
        if not all_data:
            return False

        # Extract values and timestamps
        values, timestamps = self._extract_values(all_data, jmespath_expr)
        if not values or len(values) != len(timestamps):
            return False

        # Filter data by timeframe if specified
        if timeframe_seconds is not None and len(timestamps) > 0:
            # Find the latest timestamp
            try:
                # Convert timestamps to datetime objects for comparison
                datetime_objects = []
                invalid_timestamp_count = 0
                for ts in timestamps:
                    try:
                        # Handle ISO format timestamps
                        dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        datetime_objects.append(dt)
                    except (ValueError, TypeError, AttributeError):
                        # Skip invalid timestamps
                        datetime_objects.append(None)
                        invalid_timestamp_count += 1

                # Filter out None values and find latest time
                valid_datetimes = [dt for dt in datetime_objects if dt is not None]
                if valid_datetimes:
                    latest_time = max(valid_datetimes)
                    # Calculate cutoff time
                    cutoff_time = latest_time - datetime.timedelta(
                        seconds=timeframe_seconds
                    )

                    # Filter data points within the timeframe
                    filtered_data = []
                    filtered_timestamps = []
                    for i, dt in enumerate(datetime_objects):
                        if dt is not None and dt >= cutoff_time:
                            filtered_data.append(values[i])
                            filtered_timestamps.append(timestamps[i])

                    # Update values and timestamps if we have filtered data
                    if filtered_data:
                        values = filtered_data
                        timestamps = filtered_timestamps
            except Exception:
                # If there's an error in filtering, fall back to using all data
                print(
                    "Error filtering data by timeframe. Using all available data instead."
                )

        # Store the data
        self.data_points = values
        self.timestamps = timestamps

        # Calculate min and max values for scaling
        self.min_value = min(values)
        self.max_value = max(values)

        # Set title - include the jmespath expression and timeframe if applicable
        title = f"Data Visualization: {jmespath_expr}"
        if timeframe_seconds is not None:
            title += f" (Last {timeframe_seconds} seconds)"
        self.title = title

        # Store the latest value for display
        self.latest_value = values[-1] if values else None

        return True

    def _draw_axes(self, win, height: int, width: int):
        """Draw the X and Y axes"""
        # Draw X axis
        win.addch(height - 3, 2, curses.ACS_LTEE)
        win.hline(height - 3, 3, curses.ACS_HLINE, width - 6)
        win.addch(height - 3, width - 3, curses.ACS_RTEE)

        # Draw Y axis
        win.addch(2, 2, curses.ACS_TTEE)
        win.vline(3, 2, curses.ACS_VLINE, height - 6)
        win.addch(height - 3, 2, curses.ACS_LTEE)

        # Add labels
        win.addstr(height - 2, width // 2 - 4, "Time →")
        win.addstr(height // 2, 0, "Value", curses.A_VERTICAL)

        # Add min and max values on Y axis
        if self.max_value != self.min_value:
            win.addstr(2, 4, f"{self.max_value:.1f}")
            win.addstr(height - 4, 4, f"{self.min_value:.1f}")

        # Add timestamp information to X axis if we have timestamps
        if self.timestamps and len(self.timestamps) > 1:
            # Display timestamp at start, middle and end points
            display_points = [0, len(self.timestamps) // 2, len(self.timestamps) - 1]
            x_scale = (width - 6) / max(1, len(self.data_points) - 1)

            for i in display_points:
                if i < len(self.timestamps):
                    # Format timestamp if it exists
                    timestamp = self.timestamps[i]
                    if timestamp:
                        # Try to parse the timestamp and format it nicely
                        try:
                            # If timestamp is in ISO format, parse and format it
                            dt = datetime.datetime.fromisoformat(
                                timestamp.replace("Z", "+00:00")
                            )
                            formatted_time = dt.strftime("%H:%M:%S")
                        except (ValueError, TypeError):
                            # If parsing fails, use the original timestamp (truncated if needed)
                            formatted_time = str(timestamp)
                            if len(formatted_time) > 10:
                                formatted_time = formatted_time[:10] + "..."

                        # Calculate position and display timestamp
                        x_pos = int(3 + i * x_scale)
                        # Center the text at the x position
                        x_pos = max(
                            3,
                            min(
                                width - len(formatted_time) - 3,
                                x_pos - len(formatted_time) // 2,
                            ),
                        )
                        try:
                            win.addstr(height - 2, x_pos, formatted_time)
                        except:
                            # If we can't write at this position (e.g., near the edge), skip it
                            pass

    def _draw_graph(self, win, height: int, width: int):
        """Draw the graph with the data points"""
        if not self.data_points:
            return

        # Calculate scaling factors to use full width
        x_scale = (width - 6) / max(1, len(self.data_points) - 1)

        value_range = max(
            0.1, self.max_value - self.min_value
        )  # Avoid division by zero
        y_scale = (height - 6) / value_range

        # Calculate all point coordinates first
        coords = []
        for i, value in enumerate(self.data_points):
            # Calculate screen coordinates
            x = int(3 + i * x_scale)
            y = int(height - 4 - ((value - self.min_value) * y_scale))

            # Keep coordinates within bounds
            x = max(3, min(width - 4, x))
            y = max(3, min(height - 4, y))

            coords.append((x, y))

        # Set up color regions - divide the points into three age groups
        total_points = len(coords)
        if total_points > 0:
            old_threshold = total_points // 3
            new_threshold = total_points - old_threshold

            # Function to get color based on index position
            def get_color_pair(idx):
                if idx < old_threshold:
                    return 1  # Yellow (oldest)
                elif idx < new_threshold:
                    return 2  # Green (middle age)
                else:
                    return 3  # Blue (newest)

            # Draw spline curves connecting points with color gradient
            if len(coords) >= 4:
                # Need at least 4 points for a cubic spline
                for i in range(1, len(coords) - 2):
                    x0, y0 = coords[i - 1]
                    x1, y1 = coords[i]
                    x2, y2 = coords[i + 1]
                    x3, y3 = coords[i + 2]

                    # Get color for this segment
                    color_pair = get_color_pair(i)
                    if curses.has_colors():
                        win.attron(curses.color_pair(color_pair))

                    # Calculate spline points
                    spline_points = self._calculate_spline_points(
                        x0, y0, x1, y1, x2, y2, x3, y3
                    )

                    # Draw the spline segment
                    last_px, last_py = None, None
                    for px, py in spline_points:
                        # Keep coordinates in bounds and convert to integers only at final drawing stage
                        px_bounded = max(3, min(width - 4, px))
                        py_bounded = max(3, min(height - 4, py))
                        px_int = int(round(px_bounded))
                        py_int = int(round(py_bounded))

                        if last_px is not None and last_py is not None:
                            # Draw very thin line (dots) - pass floating point values to drawing function
                            self._draw_line(
                                win, last_py, last_px, py_bounded, px_bounded, "·"
                            )

                        last_px, last_py = px_bounded, py_bounded

                    if curses.has_colors():
                        win.attroff(curses.color_pair(color_pair))
            elif len(coords) > 1:
                # If we don't have enough points for a spline, connect with straight lines
                for i in range(1, len(coords)):
                    x1, y1 = coords[i - 1]
                    x2, y2 = coords[i]

                    # Get color for this segment
                    color_pair = get_color_pair(i - 1)
                    if curses.has_colors():
                        win.attron(curses.color_pair(color_pair))

                    self._draw_line(win, y1, x1, y2, x2, "·")

                    if curses.has_colors():
                        win.attroff(curses.color_pair(color_pair))

            # Plot points as X markers over the lines with appropriate colors
            for i, (x, y) in enumerate(coords):
                # Get color for this point
                color_pair = get_color_pair(i)

                if curses.has_colors():
                    win.attron(curses.color_pair(color_pair))

                # Draw the point as an 'x'
                try:
                    win.addch(y, x, "x")
                except:
                    pass

                if curses.has_colors():
                    win.attroff(curses.color_pair(color_pair))

    def _draw_line(self, win, y0, x0, y1, x1, char: str = "·"):
        """Draw a line between two points with high precision using floating point calculations"""
        # Convert to float to ensure floating point division
        x0, y0, x1, y1 = float(x0), float(y0), float(x1), float(y1)

        # Determine if the line is steep (|slope| > 1)
        steep = abs(y1 - y0) > abs(x1 - x0)

        if steep:
            # If steep, swap x and y
            x0, y0 = y0, x0
            x1, y1 = y1, x1

        # Ensure x is increasing
        if x0 > x1:
            x0, x1 = x1, x0
            y0, y1 = y1, y0

        # Calculate dx and slope
        dx = x1 - x0
        if dx == 0:
            # Vertical line case
            slope = 0  # Arbitrary, as we'll handle it specially
        else:
            slope = (y1 - y0) / dx

        # For high precision drawing, use smaller steps
        # The smaller the step size, the more accurate the line
        step_size = 0.5  # Smaller step size for higher density

        # Track points already drawn to avoid duplicates
        drawn_points = set()

        # Draw the line using floating point stepping
        x = x0
        y = y0
        while x <= x1:
            # Calculate point positions with proper rounding
            if steep:
                plot_x, plot_y = int(round(y)), int(round(x))
            else:
                plot_x, plot_y = int(round(x)), int(round(y))

            # Only draw if we haven't already drawn at this position
            point = (plot_y, plot_x)
            if point not in drawn_points:
                drawn_points.add(point)
                try:
                    win.addch(plot_y, plot_x, char)
                except:
                    pass

            # Step along the line
            x += step_size
            y += slope * step_size

    def visualize(
        self,
        data_dir: str,
        jmespath_expr: str,
        timeframe_seconds: Optional[int] = None,
        ui_mode: bool = False,
    ) -> str:
        """
        Visualize time series data using ncurses or markdown format

        Args:
            data_dir: Directory containing the JSON data files
            jmespath_expr: JMESPath expression to extract the value to plot (default, for example: "sources.SinusSource.values.sinus.value")
            timeframe_seconds: Optional timeframe in seconds to display (e.g., 15, 30)
                              If None, displays all available data
            ui_mode: If True, returns a markdown representation instead of using ncurses

        Returns:
            Result message or markdown graph
        """
        # Auto-select UI mode on Windows if curses is not available
        if not ui_mode and (
            curses is None
            or platform.system() == "Windows"
            and not hasattr(curses, "wrapper")
        ):
            ui_mode = True
            print("Note: Using UI mode instead of terminal visualization on Windows")
        # Store data_dir and jmespath_expr for timeframe selection
        self.data_dir = data_dir
        self.jmespath_expr = jmespath_expr
        self.current_timeframe = timeframe_seconds

        # Prepare the data
        if not self._prepare_data(data_dir, jmespath_expr, timeframe_seconds):
            timeframe_msg = (
                f" for the last {timeframe_seconds} seconds"
                if timeframe_seconds
                else ""
            )
            return f"❌ Failed to prepare data from {data_dir} using expression '{jmespath_expr}'{timeframe_msg}"

        if not self.data_points:
            timeframe_msg = (
                f" for the last {timeframe_seconds} seconds"
                if timeframe_seconds
                else ""
            )
            return f"❌ No data points found in {data_dir} using expression '{jmespath_expr}'{timeframe_msg}"

        # If in UI mode, generate markdown representation
        if ui_mode:
            return self._generate_markdown_graph()

        # Otherwise initialize ncurses for terminal display
        try:
            # Wrapper to ensure proper cleanup
            result = curses.wrapper(self._visualize_with_curses)
            return result
        except Exception as e:
            return f"❌ Error during visualization: {str(e)}"

    def _visualize_with_curses(self, stdscr):
        """Handle the ncurses visualization"""
        # Clear screen
        stdscr.clear()
        curses.curs_set(0)  # Hide cursor

        # Set up colors if available
        if curses.has_colors():
            curses.start_color()
            # Color scheme: older (yellow) -> middle (green) -> newer (blue)
            curses.init_pair(1, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # Oldest data
            curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Middle data
            curses.init_pair(3, curses.COLOR_BLUE, curses.COLOR_BLACK)  # Newest data
            curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_BLACK)  # Text and axes

        # Get screen dimensions
        height, width = stdscr.getmaxyx()

        # Draw border first
        stdscr.box()

        # Draw title with jmespath expression inside the border
        if curses.has_colors():
            stdscr.attron(curses.color_pair(4) | curses.A_BOLD)
        stdscr.addstr(1, (width - len(self.title)) // 2, self.title)
        if curses.has_colors():
            stdscr.attroff(curses.color_pair(4) | curses.A_BOLD)

        # Add latest value as subtitle if available
        if hasattr(self, "latest_value") and self.latest_value is not None:
            subtitle = f"Latest Value: {self.latest_value:.2f}"
            if curses.has_colors():
                stdscr.attron(curses.color_pair(3))  # Use blue (newest) color
            stdscr.addstr(2, (width - len(subtitle)) // 2, subtitle)
            if curses.has_colors():
                stdscr.attroff(curses.color_pair(3))

        # Draw axes
        self._draw_axes(stdscr, height, width)

        # Draw the graph with color
        self._draw_graph(stdscr, height, width)

        # Add instructions
        instruction = "Press T for timeframe options | Any other key to exit"
        stdscr.addstr(height - 1, (width - len(instruction)) // 2, instruction)

        # Add stats
        stats = f"Points: {len(self.data_points)} | Min: {self.min_value:.2f} | Max: {self.max_value:.2f}"
        stdscr.addstr(3, (width - len(stats)) // 2, stats)

        # Refresh and wait for keypress
        stdscr.refresh()
        key = stdscr.getch()

        # If user presses 't' or 'T', show timeframe selection menu
        if key in [116, 84]:  # ASCII for 't' and 'T'
            return self._show_timeframe_menu(stdscr)

        return f"✅ Successfully visualized {len(self.data_points)} data points from expression: '{self.title}'"

    def _generate_timeseries_graph(self) -> str:
        """Generate a time series graph using matplotlib and encode as base64 for embedding in markdown"""
        if not self.data_points or len(self.data_points) < 2:
            return ""

        # Convert timestamps to datetime objects
        datetime_objects = []
        for ts in self.timestamps:
            try:
                dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                datetime_objects.append(dt)
            except (ValueError, TypeError, AttributeError):
                # Use current time as fallback for invalid timestamps
                datetime_objects.append(datetime.datetime.now())

        # Create a new figure with appropriate size for embedding
        plt.figure(figsize=(10, 6))

        # Create the time series plot
        plt.plot(
            datetime_objects,
            self.data_points,
            "-o",
            color="#4f46e5",
            linewidth=2,
            markersize=4,
        )

        # Add labels and title
        plt.title(f"Time Series: {self.jmespath_expr}", fontsize=14, pad=10)
        plt.xlabel("Time", fontsize=12, labelpad=10)
        plt.ylabel("Value", fontsize=12, labelpad=10)

        # Format x-axis dates
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        plt.xticks(rotation=45)

        # Add grid for better readability
        plt.grid(True, linestyle="--", alpha=0.7)

        # Add trend line
        if len(self.data_points) > 2:
            try:
                import numpy as np
                from scipy import stats

                # Simple linear regression for trend
                x = np.arange(len(self.data_points))
                slope, intercept, r_value, p_value, std_err = stats.linregress(
                    x, self.data_points
                )
                trend_line = intercept + slope * x
                plt.plot(
                    datetime_objects,
                    trend_line,
                    "r--",
                    alpha=0.6,
                    label=f"Trend (slope: {slope:.3f})",
                )
                plt.legend(loc="best")
            except ImportError:
                # If scipy is not available, skip trend line
                pass

        # Tight layout to ensure everything fits
        plt.tight_layout()

        # Save the plot to a bytes buffer
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=100)
        buf.seek(0)

        # Encode the image as base64 for embedding in markdown
        img_str = base64.b64encode(buf.getvalue()).decode("ascii")

        # Close the plot to free memory
        plt.close()

        # Return the base64 encoded image using direct HTML (more compatible with UI renderers)
        return f'<img src="data:image/png;base64,{img_str}" alt="Time Series Graph" style="max-width: 100%;">'

    def _generate_markdown_graph(self) -> str:
        """Generate a markdown representation of the graph for UI mode"""
        if not self.data_points:
            return "❌ No data points to visualize"

        # Create a simplified version focused on readability in the web UI

        # Add title and metadata
        result = f"## {self.title}\n\n"

        # Add statistics
        result += f"**Points:** {len(self.data_points)} | **Min:** {self.min_value:.2f} | **Max:** {self.max_value:.2f}"
        if hasattr(self, "latest_value") and self.latest_value is not None:
            result += f" | **Latest:** {self.latest_value:.2f}"
        result += "\n\n"

        # Add timeframe info
        if self.current_timeframe:
            result += f"*Showing last {self.current_timeframe} seconds of data*\n\n"
        elif self.timestamps and len(self.timestamps) > 1:
            try:
                start_time = datetime.datetime.fromisoformat(
                    self.timestamps[0].replace("Z", "+00:00")
                ).strftime("%H:%M:%S")
                end_time = datetime.datetime.fromisoformat(
                    self.timestamps[-1].replace("Z", "+00:00")
                ).strftime("%H:%M:%S")
                result += f"*Data from {start_time} to {end_time}*\n\n"
            except:
                pass

        # Generate the time series graph and data table side by side using HTML
        result += "<div style='display: flex; flex-wrap: wrap; gap: 20px; align-items: flex-start;'>\n\n"

        # Left column - Time Series Graph
        result += "<div style='flex: 1; min-width: 400px;'>\n\n"
        result += "<h3>Time Series Graph</h3>\n\n"
        graph_image = self._generate_timeseries_graph()
        if graph_image:
            result += graph_image + "\n\n"
        else:
            result += "*Not enough data points to generate a graph*\n\n"
        result += "</div>\n\n"

        # Right column - Data Table - using HTML table instead of markdown for consistency with HTML layout
        result += "<div style='flex: 1; min-width: 300px;'>\n\n"
        result += "<h3>Data Points</h3>\n\n"

        # Start HTML table with styling that matches markdown tables
        result += (
            "<table style='border-collapse: collapse; width: 100%; margin: 6px 0;'>\n"
        )
        result += "<thead style='position: sticky; top: 0; background-color: #f8f9fa; z-index: 1;'>\n"
        result += "<tr>\n"
        result += "<th style='border: 1px solid #ddd; padding: 4px; text-align: left;'>#</th>\n"
        result += "<th style='border: 1px solid #ddd; padding: 4px; text-align: left;'>Value</th>\n"
        result += "<th style='border: 1px solid #ddd; padding: 4px; text-align: left;'>Timestamp</th>\n"
        result += "</tr>\n"
        result += "</thead>\n"
        result += "<tbody>\n"

        # Display data points (limit to max 20 for readability)
        display_count = min(20, len(self.data_points))
        step = max(1, len(self.data_points) // display_count)

        indices_to_show = []
        # Always show first, last and some points in between
        if len(self.data_points) > 0:
            indices_to_show.append(0)  # First point
        if len(self.data_points) > 1:
            indices_to_show.append(len(self.data_points) - 1)  # Last point

        # Add evenly distributed points in the middle
        for i in range(step, len(self.data_points) - 1, step):
            if len(indices_to_show) < display_count:
                indices_to_show.append(i)

        # Sort indices to display in order
        indices_to_show.sort()

        # Add data rows
        for idx in indices_to_show:
            value = self.data_points[idx]
            timestamp = ""
            if idx < len(self.timestamps) and self.timestamps[idx]:
                try:
                    dt = datetime.datetime.fromisoformat(
                        self.timestamps[idx].replace("Z", "+00:00")
                    )
                    timestamp = dt.strftime("%H:%M:%S")
                except:
                    timestamp = str(self.timestamps[idx])[:10]

            result += "<tr>\n"
            result += f"<td style='border: 1px solid #ddd; padding: 4px; text-align: left;'>{idx+1}</td>\n"
            result += f"<td style='border: 1px solid #ddd; padding: 4px; text-align: left;'>{value:.2f}</td>\n"
            result += f"<td style='border: 1px solid #ddd; padding: 4px; text-align: left;'>{timestamp}</td>\n"
            result += "</tr>\n"

        # Close HTML table
        result += "</tbody>\n"
        result += "</table>\n"

        # Add note if we didn't show all points
        if len(self.data_points) > display_count:
            result += f"\n<p><em>Showing {len(indices_to_show)} of {len(self.data_points)} data points</em></p>\n"

        result += "</div>\n\n"
        result += "</div>\n\n"

        # Add trend indicators outside the flex container
        if len(self.data_points) > 1:
            first_value = self.data_points[0]
            last_value = self.data_points[-1]
            change = last_value - first_value
            percent_change = (
                (change / abs(first_value)) * 100 if first_value != 0 else 0
            )

            result += "\n<h3>Trend</h3>\n\n"
            if change > 0:
                result += f"📈 <strong>Increasing</strong>: +{change:.2f} (+{percent_change:.1f}%)<br>\n"
            elif change < 0:
                result += f"📉 <strong>Decreasing</strong>: {change:.2f} ({percent_change:.1f}%)<br>\n"
            else:
                result += "➡️ <strong>Stable</strong>: No change<br>\n"

        return result

    def _show_timeframe_menu(self, stdscr):
        """Show a menu for selecting different timeframes"""
        # Define available timeframe options (in seconds)
        timeframes = [15, 30, 60, 120, 300, 0]  # 0 means all data

        # Clear screen
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        # Draw border
        stdscr.box()

        # Draw title
        title = "Select Timeframe"
        stdscr.addstr(1, (width - len(title)) // 2, title, curses.A_BOLD)

        # Draw instructions
        instruction = "Use arrow keys to select, Enter to confirm"
        stdscr.addstr(3, (width - len(instruction)) // 2, instruction)

        # Prepare timeframe labels
        timeframe_labels = [
            "Last 15 seconds",
            "Last 30 seconds",
            "Last 1 minute",
            "Last 2 minutes",
            "Last 5 minutes",
            "All data",
        ]

        # Find current selection index (if applicable)
        current_option = 0
        if self.current_timeframe is not None:
            try:
                current_option = timeframes.index(self.current_timeframe)
            except ValueError:
                # If current timeframe is not in our predefined list, default to first option
                pass
        else:
            current_option = len(timeframes) - 1  # "All data" option

        # Main menu loop
        while True:
            # Display all options
            for i, label in enumerate(timeframe_labels):
                y = 5 + i
                x = (width - len(label)) // 2

                # Highlight the selected option
                if i == current_option:
                    stdscr.attron(curses.A_REVERSE)

                stdscr.addstr(y, x, label)

                if i == current_option:
                    stdscr.attroff(curses.A_REVERSE)

            # Handle key presses
            key = stdscr.getch()

            if key == curses.KEY_UP and current_option > 0:
                current_option -= 1
            elif key == curses.KEY_DOWN and current_option < len(timeframe_labels) - 1:
                current_option += 1
            elif key in [10, 13]:  # Enter key
                # User made a selection
                selected_timeframe = timeframes[current_option]

                # Return to visualization with the new timeframe
                if selected_timeframe == 0:  # All data
                    self._prepare_data(self.data_dir, self.jmespath_expr)
                else:
                    self._prepare_data(
                        self.data_dir, self.jmespath_expr, selected_timeframe
                    )

                self.current_timeframe = (
                    selected_timeframe if selected_timeframe > 0 else None
                )

                # Redraw the visualization
                stdscr.clear()
                return self._visualize_with_curses(stdscr)
            elif key == 27:  # Escape key
                # Cancel and return to the visualization
                stdscr.clear()
                return self._visualize_with_curses(stdscr)


def visualize_time_series(
    data_dir: str,
    jmespath_expr: str,
    timeframe_seconds: Optional[int] = None,
    ui_mode: bool = False,
) -> str:
    """
    Visualize time series data from SFC data files

    Args:
        data_dir: Directory containing the JSON data files
        jmespath_expr: JMESPath expression to extract the value to plot (e.g., "sources.SinusSource.values.sinus.value")
        timeframe_seconds: Optional timeframe in seconds to display (e.g., 15, 30)
                          If None, displays all available data
        ui_mode: If True, returns a markdown representation instead of using ncurses

    Returns:
        Result message or markdown graph
    """
    # First, check if the directory exists
    if not os.path.isdir(data_dir):
        return f"❌ Directory not found: {data_dir}"

    # Check if the directory contains any JSON files (recursively)
    json_files = glob.glob(os.path.join(data_dir, "**", "*.json"), recursive=True)
    if not json_files:
        return f"❌ No JSON files found in {data_dir} (including subdirectories)"

    # Initialize the visualizer and run it
    visualizer = DataVisualizer()
    result = visualizer.visualize(data_dir, jmespath_expr, timeframe_seconds, ui_mode)

    return result


if __name__ == "__main__":
    import sys
    import argparse

    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(
        description="Visualize time series data from SFC data files"
    )
    parser.add_argument("data_dir", help="Directory containing the JSON data files")
    parser.add_argument(
        "jmespath_expr", help="JMESPath expression to extract the value to plot"
    )
    parser.add_argument(
        "--timeframe",
        "-t",
        type=int,
        help="Timeframe in seconds to display (e.g., 15, 30)",
    )

    # Parse arguments
    args = parser.parse_args()

    # Run visualization
    result = visualize_time_series(args.data_dir, args.jmespath_expr, args.timeframe)
    print(result)
