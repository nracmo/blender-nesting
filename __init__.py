import bpy
import mathutils
import math

bl_info = {
    "name": "Blender Nesting Add-on",
    "author": "Camron",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "3D View > Sidebar > Nesting Tab",
    "description": "Nests selected 3D objects into a designated cube volume. (December 31, 2025)",
    "warning": "",
    "doc_url": "",
    "category": "Object",
}

class NESTING_OT_PackObjects(bpy.types.Operator):
    """Pack selected objects into the active object (container)"""
    bl_idname = "nesting.pack_objects"
    bl_label = "Pack Objects"
    bl_options = {'REGISTER', 'UNDO'}

    def get_world_bounding_box(self, obj):
        # Helper for static objects
        world_matrix = obj.matrix_world
        min_x, min_y, min_z = [float('inf')] * 3
        max_x, max_y, max_z = [float('-inf')] * 3
        for corner in obj.bound_box:
            world_corner = world_matrix @ mathutils.Vector(corner)
            min_x = min(min_x, world_corner.x)
            max_x = max(max_x, world_corner.x)
            min_y = min(min_y, world_corner.y)
            max_y = max(max_y, world_corner.y)
            min_z = min(min_z, world_corner.z)
            max_z = max(max_z, world_corner.z)
        return mathutils.Vector((min_x, min_y, min_z)), mathutils.Vector((max_x, max_y, max_z))

    def get_rotated_aabb_dims(self, obj, rotation_euler):
        # Calculate AABB dimensions if object were rotated by rotation_euler (absolute)
        loc, _, scale = obj.matrix_world.decompose()
        new_rot_quat = rotation_euler.to_quaternion()
        new_matrix = mathutils.Matrix.LocRotScale(loc, new_rot_quat, scale)
        
        min_x, min_y, min_z = [float('inf')] * 3
        max_x, max_y, max_z = [float('-inf')] * 3
        
        for corner in obj.bound_box:
            world_corner = new_matrix @ mathutils.Vector(corner)
            min_x = min(min_x, world_corner.x)
            max_x = max(max_x, world_corner.x)
            min_y = min(min_y, world_corner.y)
            max_y = max(max_y, world_corner.y)
            min_z = min(min_z, world_corner.z)
            max_z = max(max_z, world_corner.z)
            
        return max_x - min_x, max_y - min_y, max_z - min_z

    def generate_candidates(self, obj, mode, attempts, step_deg):
        import random
        candidates = [] # List of ( (dx, dy, dz), euler )
        
        current_euler = obj.rotation_euler.copy()
        
        if mode == 'Z_AXIS':
            # V5 Behavior: Original + 90 degrees Z
            candidates.append((self.get_rotated_aabb_dims(obj, current_euler), current_euler))
            
            rot_90 = current_euler.copy()
            rot_90.z += 1.570796 # 90 degrees
            candidates.append((self.get_rotated_aabb_dims(obj, rot_90), rot_90))
                
        elif mode == 'FULL_90':
            # Try 90 degree increments on X, Y, Z. 
            axes = [0, 1.570796, 3.14159, 4.71239]
            unique_dims = set()
            
            for x in axes:
                for y in axes:
                    for z in axes:
                        eul = mathutils.Euler((x, y, z), 'XYZ')
                        dims = self.get_rotated_aabb_dims(obj, eul)
                        # Filter very similar dimensions
                        dims_rounded = (round(dims[0], 4), round(dims[1], 4), round(dims[2], 4))
                        if dims_rounded not in unique_dims:
                            candidates.append((dims, eul))
                            unique_dims.add(dims_rounded)
            
        elif mode == 'RANDOM':
            # Original always included
            candidates.append((self.get_rotated_aabb_dims(obj, current_euler), current_euler))
            
            if step_deg < 1: step_deg = 1
            step_rad = math.radians(step_deg)
            
            for _ in range(attempts):
                # Generate random indices for steps
                # 360 / 5 = 72 steps
                max_steps = int(360 / step_deg)
                
                sx = random.randint(0, max_steps)
                sy = random.randint(0, max_steps)
                sz = random.randint(0, max_steps)
                
                rx = sx * step_rad
                ry = sy * step_rad
                rz = sz * step_rad
                
                eul = mathutils.Euler((rx, ry, rz), 'XYZ')
                dims = self.get_rotated_aabb_dims(obj, eul)
                candidates.append((dims, eul))
            
        # Sort by Volume (Smallest volume first = most efficient packing usually)
        candidates.sort(key=lambda x: x[0][0] * x[0][1] * x[0][2])
            
        return candidates

    def check_collision(self, new_obj_min, new_obj_max, packed_objects_bbs, padding):
        for packed_min, packed_max in packed_objects_bbs:
            # Check for overlap on all axes, considering padding
            if (new_obj_max.x - padding > packed_min.x and new_obj_min.x + padding < packed_max.x and
                new_obj_max.y - padding > packed_min.y and new_obj_min.y + padding < packed_max.y and
                new_obj_max.z - padding > packed_min.z and new_obj_min.z + padding < packed_max.z):
                return True # Collision detected
        return False # No collision

    def execute(self, context):
        self.report({'INFO'}, "Packing objects...")
        
        mode = context.scene.nesting_rotation_mode
        attempts_count = context.scene.nesting_random_attempts
        step_deg = context.scene.nesting_rotation_step
        padding = context.scene.nesting_padding
        selected_objects = context.selected_objects
        active_object = context.scene.nesting_container_object

        if not active_object or active_object.type != 'MESH':
            self.report({'ERROR'}, "Please assign a mesh container object in the Nesting panel.")
            return {'CANCELLED'}

        if not selected_objects:
            self.report({'ERROR'}, "No objects selected to pack.")
            return {'CANCELLED'}

        objects_to_pack = [obj for obj in selected_objects if obj != active_object]

        if not objects_to_pack:
            self.report({'ERROR'}, "No objects to pack selected.")
            return {'CANCELLED'}

        # Get container dimensions in world space
        container_min_ws, container_max_ws = self.get_world_bounding_box(active_object)
        
        # Prepare object data with candidates
        object_data = []
        for obj in objects_to_pack:
            candidates = self.generate_candidates(obj, mode, attempts_count, step_deg)
            # Use smallest volume for sorting order
            best_vol = min([c[0][0]*c[0][1]*c[0][2] for c in candidates])
            object_data.append({'obj': obj, 'candidates': candidates, 'best_vol': best_vol})

        # Sort objects by volume (descending) - Pack biggest items first
        object_data.sort(key=lambda x: x['best_vol'], reverse=True)

        # Anchor Points Algorithm (Bottom-Left heuristic)
        # Start with the bottom-front-left corner of the container
        anchor_points = [container_min_ws + mathutils.Vector((padding, padding, padding))]
        
        packed_objects_bbs = [] 
        packed_count = 0
        failed_objects = []

        for data in object_data:
            obj = data['obj']
            candidates = data['candidates'] 

            packed = False
            
            # Sort anchor points: Prefer lower Z, then lower Y, then lower X
            # This fills the bottom layer first, then moves back, then up.
            anchor_points.sort(key=lambda p: (round(p.z, 4), round(p.y, 4), round(p.x, 4)))
            
            # Optimization: Limit candidate checks if too many anchors? 
            # For now, we try all candidates at all anchors until fit.
            # To speed up, we can limit rotation candidates to top 10 best volumes?
            # candidates = candidates[:10] 

            for (dims_x, dims_y, dims_z), euler_rot in candidates:
                
                for pt in anchor_points:
                    # Check Container Bounds
                    if (pt.x + dims_x + padding > container_max_ws.x or
                        pt.y + dims_y + padding > container_max_ws.y or
                        pt.z + dims_z + padding > container_max_ws.z):
                        continue # Fits out of bounds

                    proposed_min_ws = pt
                    proposed_max_ws = mathutils.Vector((pt.x + dims_x, pt.y + dims_y, pt.z + dims_z))

                    # Check Collision
                    if not self.check_collision(proposed_min_ws, proposed_max_ws, packed_objects_bbs, padding):
                        # --- VALID SPOT ---
                        
                        # Apply Rotation
                        obj.rotation_euler = euler_rot
                        
                        # Place Object
                        # Center object in the proposed box
                        # (Standard logic to handle pivot offset)
                        context.view_layer.update() 
                        c_min, c_max = self.get_world_bounding_box(obj)
                        current_world_center = c_min + (c_max - c_min) / 2
                        target_center = proposed_min_ws + (proposed_max_ws - proposed_min_ws) / 2
                        diff = target_center - current_world_center
                        obj.location += diff
                        
                        self.report({'INFO'}, f"Packed {obj.name}")
                        
                        # Register success
                        packed_objects_bbs.append((proposed_min_ws, proposed_max_ws))
                        packed_count += 1
                        packed = True
                        
                        # Add new Anchor Points derived from this placement
                        # We add points at the extent of this object in X, Y, Z directions relative to its origin pt
                        # Point 1: Shift X (Right of object)
                        p1 = mathutils.Vector((proposed_max_ws.x + padding, proposed_min_ws.y, proposed_min_ws.z))
                        # Point 2: Shift Y (Behind object)
                        p2 = mathutils.Vector((proposed_min_ws.x, proposed_max_ws.y + padding, proposed_min_ws.z))
                        # Point 3: Shift Z (Above object)
                        p3 = mathutils.Vector((proposed_min_ws.x, proposed_min_ws.y, proposed_max_ws.z + padding))
                        
                        new_points = [p1, p2, p3]
                        
                        # Add valid new points
                        for np in new_points:
                            # Basic bounds check to avoid adding useless points
                            if (np.x < container_max_ws.x and 
                                np.y < container_max_ws.y and 
                                np.z < container_max_ws.z):
                                anchor_points.append(np)
                        
                        # Note: We do NOT remove the 'pt' we used from anchor_points list? 
                        # Ideally we should, because it's "used". 
                        # However, strictly speaking, a point is just a coordinate. 
                        # If we don't remove it, next object might check it and immediately collide.
                        # Efficiency: Remove it.
                        anchor_points.remove(pt)
                        
                        break # Break anchor loop
                
                if packed:
                    break # Break candidate loop

            if not packed:
                self.report({'WARNING'}, f"Could not pack {obj.name}")
                failed_objects.append(obj.name)

        if failed_objects:
             self.report({'WARNING'}, f"Finished with errors. Failed to pack: {', '.join(failed_objects)}")
        else:
             self.report({'INFO'}, f"Successfully packed {packed_count} objects!")
             
        return {'FINISHED'}


class NESTING_PT_NestingPanel(bpy.types.Panel):
    """Creates a Panel in the 3D Viewport Sidebar"""
    bl_label = "Nesting"
    bl_idname = "NESTING_PT_NestingPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Tool" # Changed from "Nesting" to "Tool" for common placement

    def draw(self, context):
        layout = self.layout
        
        col = layout.column(align=True)
        col.label(text="Container:")
        col.prop(context.scene, "nesting_container_object", text="")

        layout.separator()
        col.prop(context.scene, "nesting_rotation_mode", text="Rotation Mode")
        
        if context.scene.nesting_rotation_mode == 'RANDOM':
            col.prop(context.scene, "nesting_rotation_step", text="Step Angle")
            col.prop(context.scene, "nesting_random_attempts", text="Samples")
            
        col.prop(context.scene, "nesting_padding", text="Spacing")

        layout.label(text="Objects to Pack:")
        
        # Display selected objects (excluding the container)
        objects_to_display = [obj for obj in context.selected_objects if obj != context.scene.nesting_container_object]
        if objects_to_display:
            for obj in objects_to_display:
                layout.label(text=obj.name)
        else:
            layout.label(text="None selected to pack")

        layout.operator(NESTING_OT_PackObjects.bl_idname, text="Pack Selected Objects")


# Register and unregister functions
def register():
    bpy.utils.register_class(NESTING_OT_PackObjects)
    bpy.utils.register_class(NESTING_PT_NestingPanel)
    
    bpy.types.Scene.nesting_container_object = bpy.props.PointerProperty(
        name="Container Object",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH'
    )
    
    bpy.types.Scene.nesting_rotation_mode = bpy.props.EnumProperty(
        name="Rotation Mode",
        description="How objects should be rotated to fit",
        items=[
            ('Z_AXIS', "Z-Axis (90°)", "Rotate 90 degrees around Z only"),
            ('FULL_90', "6-Sided (90°)", "Try orthogonal orientations"),
            ('RANDOM', "Random (Best Fit)", "Try random orientations at stepped intervals")
        ],
        default='Z_AXIS'
    )
    
    bpy.types.Scene.nesting_rotation_step = bpy.props.IntProperty(
        name="Rotation Step",
        description="Angle step size in degrees for Random rotation",
        default=5,
        min=1,
        max=180
    )
    
    bpy.types.Scene.nesting_random_attempts = bpy.props.IntProperty(
        name="Random Samples",
        description="Number of random orientations to try per object",
        default=10,
        min=1,
        max=100
    )
    
    bpy.types.Scene.nesting_padding = bpy.props.FloatProperty(
        name="Spacing",
        description="Minimum space between objects",
        default=0.01,
        min=0.0,
        soft_max=1.0,
        unit='LENGTH'
    )


def unregister():
    bpy.utils.unregister_class(NESTING_OT_PackObjects)
    bpy.utils.unregister_class(NESTING_PT_NestingPanel)
    del bpy.types.Scene.nesting_container_object
    del bpy.types.Scene.nesting_rotation_mode
    del bpy.types.Scene.nesting_rotation_step
    del bpy.types.Scene.nesting_random_attempts
    del bpy.types.Scene.nesting_padding

if __name__ == "__main__":
    register()