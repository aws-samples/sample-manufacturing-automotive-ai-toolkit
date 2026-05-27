/*
 * Sample automotive C code with MINOR MISRA-C violations
 * This code has only minor violations and should allow unit test generation
 */

#include <stdio.h>

// This is a C++ style comment - minor MISRA violation

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
 * Function: validate_input
 * Purpose: Validate input values for automotive sensors
 */
int validate_input(int value) {
    if (value < 0 || value > 1000) {
        return 0; // Invalid
    }
    return 1; // Valid
}

/*
 * Function: get_engine_temperature
 * Purpose: Simulate getting engine temperature reading
 */
int get_engine_temperature() {
    return 85; // Simulated temperature in Celsius
}

/*
 * Main function
 */
int main() {
    int speed = calculate_speed(100, 10);
    int is_valid = validate_input(speed);
    int temp = get_engine_temperature();
    
    if (is_valid) {
        printf("Speed: %d km/h, Engine temp: %d°C\n", speed, temp);
    }
    
    return 0;
}