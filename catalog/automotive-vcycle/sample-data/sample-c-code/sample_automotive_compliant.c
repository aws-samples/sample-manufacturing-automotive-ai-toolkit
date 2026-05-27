/*
 * Sample automotive-compliant C code
 * This code follows custom automotive coding standards and should generate unit tests
 */

#include <stdio.h>

/*
 * Function: calculate_speed
 * Purpose: Calculate vehicle speed based on distance and time
 * Parameters: distance (int), time (int)
 * Returns: speed (int) or -1 for error
 */
int calculate_speed(int distance, int time) {
    int result;
    if (time == 0) {
        result = -1; /* Error case */
    } else {
        result = distance / time;
    }
    return result;
}

/*
 * Function: validate_input
 * Purpose: Validate input values for automotive sensors
 * Parameters: value (int)
 * Returns: 1 if valid, 0 if invalid
 */
int validate_input(int value) {
    int is_valid;
    if ((value < 0) || (value > 1000)) {
        is_valid = 0; /* Invalid */
    } else {
        is_valid = 1; /* Valid */
    }
    return is_valid;
}

/*
 * Function: get_engine_temperature
 * Purpose: Simulate getting engine temperature reading
 * Returns: temperature in Celsius
 */
int get_engine_temperature(void) {
    return 85; /* Simulated temperature in Celsius */
}

/*
 * Function: check_critical_temperature
 * Purpose: Check if engine temperature is in critical range
 * Parameters: temperature (int)
 * Returns: 1 if critical, 0 if normal
 */
int check_critical_temperature(int temperature) {
    int is_critical;
    if (temperature > 100) {
        is_critical = 1; /* Critical temperature */
    } else {
        is_critical = 0; /* Normal temperature */
    }
    return is_critical;
}

/*
 * Main function
 */
int main(void) {
    int speed = calculate_speed(100, 10);
    int is_valid = validate_input(speed);
    int temp = get_engine_temperature();
    int is_critical = check_critical_temperature(temp);
    
    if (is_valid != 0) {
        (void)printf("Speed: %d km/h\n", speed);
    }
    
    if (is_critical != 0) {
        (void)printf("WARNING: Critical engine temperature: %d°C\n", temp);
    } else {
        (void)printf("Engine temperature normal: %d°C\n", temp);
    }
    
    return 0;
}