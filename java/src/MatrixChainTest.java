import java.io.*;
import java.util.*;

/**
 * Test class for Matrix Chain Multiplication Problem
 * 
 * Tests the solution with the provided sample cases and validates
 * the implementation of the large dimension deferral strategy.
 */
public class MatrixChainTest {
    
    public static void main(String[] args) {
        runTests();
    }
    
    private static void runTests() {
        System.out.println("Matrix Chain Multiplication Test Suite");
        System.out.println("======================================");
        
        // Test Case 1: From problem statement
        testCase("Test Case 1", new int[]{1, 2, 3, 4, 3}, 51);
        
        // Test Case 2: From problem statement  
        testCase("Test Case 2", new int[]{10, 20, 30}, 6000);
        
        // Additional test cases
        testCase("Test Case 3 (Basic)", new int[]{1, 2, 3}, 6);
        testCase("Test Case 4 (Uniform)", new int[]{2, 2, 2, 2}, 16);
        testCase("Test Case 5 (Increasing)", new int[]{1, 2, 3, 4, 5}, 38);
        
        System.out.println("\nAll tests completed!");
    }
    
    private static void testCase(String name, int[] dimensions, int expected) {
        System.out.println("\n" + name + ":");
        System.out.print("Dimensions: [");
        for (int i = 0; i < dimensions.length; i++) {
            System.out.print(dimensions[i]);
            if (i < dimensions.length - 1) System.out.print(", ");
        }
        System.out.println("]");
        
        // Show matrix representations
        System.out.print("Matrices: ");
        for (int i = 0; i < dimensions.length - 1; i++) {
            System.out.print("M" + (i + 1) + "(" + dimensions[i] + "x" + dimensions[i + 1] + ")");
            if (i < dimensions.length - 2) System.out.print(" × ");
        }
        System.out.println();
        
        int result = MatrixChainMultiplication.matrixChainOrder(dimensions);
        System.out.println("Result: " + result);
        System.out.println("Expected: " + expected);
        System.out.println("Status: " + (result == expected ? "PASS" : "FAIL"));
        
        if (result != expected) {
            System.out.println("WARNING: Result does not match expected value!");
        }
    }
}