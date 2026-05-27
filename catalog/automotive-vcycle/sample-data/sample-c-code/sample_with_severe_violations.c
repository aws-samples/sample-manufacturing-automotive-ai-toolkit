/*
 * Sample automotive C code with SEVERE MISRA-C violations
 * This code demonstrates high-severity violations that should block unit test generation
 */

#include <stdio.h>
#include <stdlib.h>

// This is a C++ style comment - AUTO-STYLE-001 violation

/*
 * Function: calculate_speed
 * Purpose: Calculate vehicle speed based on distance and time
 */
int calculate_speed(int distance, int time) {
    if (time == 0) {
        return -1; // Error case
    }
    return distance / time;
}

/*
 * Function: process_data
 * Purpose: Process sensor data using dynamic memory allocation (SEVERE VIOLATION)
 */
void process_data() {
    int *buffer = malloc(100 * sizeof(int)); // MISRA violation - malloc usage
    if (buffer != NULL) {
        // Process data
        for (int i = 0; i < 100; i++) {
            buffer[i] = i * 2;
        }
        free(buffer); // MISRA violation - free usage
    }
}

/*
 * Main function
 */
int main() {
    calculate_speed(100, 10); // Return value not used - MISRA violation
    process_data();
    return 0;
}