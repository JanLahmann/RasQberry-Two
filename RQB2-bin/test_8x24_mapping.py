#!/usr/bin/env python3
"""
Test script to visualize 8x24 column-major serpentine LED mapping
Helps verify the conversion from complex 4-panel layout to standard matrix
"""

def plotcalc_new(y, x):
    """New column-major serpentine mapping"""
    if x < 0 or x >= 24 or y < 0 or y >= 8:
        return -1
        
    if x % 2 == 0:  # Even columns go down (0→7)
        return x * 8 + y
    else:  # Odd columns go up (7→0)
        return x * 8 + (7 - y)

def plotcalc_old(y, x):
    """Original 4-panel mapping (from current code)"""
    # top row
    x1 = x * 4 + (0 if x % 2 == 0 else 3)
    y1 = (7 - y if x % 2 == 0 else y - 7)

    # bottom row
    x2 = 96 + (23 - x) * 4 + (0 if x % 2 == 0 else 3)
    y2 = (3 - y if x % 2 == 0 else y - 3)

    return x2 + y2 if y < 4 else x1 + y1

def visualize_mapping():
    """Show how coordinates map to LED indices for both layouts"""
    print("LED Mapping Comparison: 4-Panel vs 8x24 Column-Major Serpentine")
    print("=" * 70)
    print("Format: (y,x) -> Old_LED_Index | New_LED_Index")
    print("=" * 70)
    
    for y in range(8):
        for x in range(24):
            old_led = plotcalc_old(y, x)
            new_led = plotcalc_new(y, x)
            print(f"({y},{x:2d}) -> {old_led:3d} | {new_led:3d}", end="   ")
            if (x + 1) % 6 == 0:  # New line every 6 columns for readability
                print()
        print()

def test_corners():
    """Test corner coordinates"""
    corners = [(0,0), (0,23), (7,0), (7,23)]
    print("\nCorner Tests:")
    print("=" * 40)
    for y, x in corners:
        old_led = plotcalc_old(y, x)
        new_led = plotcalc_new(y, x)
        print(f"Corner ({y},{x:2d}): Old={old_led:3d}, New={new_led:3d}")

def test_ibm_letters():
    """Test key coordinates for IBM letters"""
    print("\nIBM Letter Coordinates:")
    print("=" * 40)
    
    # Sample coordinates for each letter
    i_coords = [(0,0), (7,5)]  # I corners
    b_coords = [(0,8), (7,12)]  # B corners  
    m_coords = [(0,16), (7,22)]  # M corners
    
    print("Letter I:")
    for y, x in i_coords:
        old_led = plotcalc_old(y, x)
        new_led = plotcalc_new(y, x)
        print(f"  ({y},{x:2d}): Old={old_led:3d}, New={new_led:3d}")
        
    print("Letter B:")
    for y, x in b_coords:
        old_led = plotcalc_old(y, x)
        new_led = plotcalc_new(y, x)
        print(f"  ({y},{x:2d}): Old={old_led:3d}, New={new_led:3d}")
        
    print("Letter M:")
    for y, x in m_coords:
        old_led = plotcalc_old(y, x)
        new_led = plotcalc_new(y, x)
        print(f"  ({y},{x:2d}): Old={old_led:3d}, New={new_led:3d}")

def show_column_pattern():
    """Show the serpentine pattern for first few columns"""
    print("\nColumn-Major Serpentine Pattern (first 4 columns):")
    print("=" * 50)
    for col in range(4):
        print(f"Column {col}:")
        for y in range(8):
            led_index = plotcalc_new(y, col)
            direction = "↓" if col % 2 == 0 else "↑"
            print(f"  y={y} -> LED {led_index:3d} {direction}")
        print()

if __name__ == "__main__":
    print("8x24 LED Matrix Mapping Test")
    print("This helps verify the conversion from 4-panel to column-major serpentine")
    print()
    
    test_corners()
    test_ibm_letters()
    show_column_pattern()
    
    # Uncomment the next line to see full mapping (lots of output!)
    # visualize_mapping()
    
    print("\nTest complete. Use this to verify LED behavior on actual hardware.")