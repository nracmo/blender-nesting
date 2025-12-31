# Blender Nesting Add-on

A powerful Blender add-on designed to efficiently nest and pack 3D objects into a designated container volume. This tool is ideal for preparing files for 3D printing (filling the build volume) or organizing scenes.

## Features

*   **Efficient Packing Algorithm:** Uses a "Bottom-Left" heuristic to fill the container volume tightly, minimizing wasted space.
*   **Collision Detection:** Ensures objects do not overlap with each other or the container boundaries.
*   **Advanced Rotation Modes:**
    *   **Z-Axis Rotation:** Rotates objects around the vertical axis to find the best fit.
    *   **6-Sided:** Tries all orthogonal orientations (90-degree turns).
    *   **Random (Best Fit):** Attempts random orientations (snapped to configurable intervals) and picks the one with the smallest footprint.
*   **Fine-Tuned Control:**
    *   **Step Angle:** Define precise rotation intervals (e.g., 5 degrees) for tighter packing of irregular shapes.
    *   **Spacing:** Adjustable padding/gap between objects to prevent fusing during printing.
    *   **Samples:** Control how many random orientations to test per object.

## Installation

1.  Download the latest release ZIP file (do not unzip it).
2.  Open Blender.
3.  Go to **Edit > Preferences > Add-ons**.
4.  Click **Install...** and select the downloaded ZIP file.
5.  Search for "Nesting" and enable **Object: Blender Nesting Add-on**.

## Usage

1.  **Prepare Container:** Create a mesh object (e.g., a Cube) representing your print volume or bounding box.
2.  **Open Panel:** In the 3D Viewport, press `N` to open the Sidebar and go to the **Tool** tab (look for the "Nesting" panel).
3.  **Assign Container:** Use the eyedropper in the panel to select your container object.
4.  **Configure Settings:**
    *   **Rotation Mode:** Choose how objects are allowed to rotate.
    *   **Spacing:** Set the minimum distance between objects.
5.  **Select Objects:** Select all the objects you want to pack (do NOT select the container itself).
6.  **Pack:** Click **Pack Selected Objects**.

## Requirements

*   Blender 2.80 or later.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
