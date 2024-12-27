import ezdxf
from ezdxf.addons import text2path
from ezdxf import bbox, path
from ezdxf.fonts import fonts
from ezdxf.addons.importer import Importer
from ezdxf.math import Matrix44

# Constants
SCALE_FACTOR = 0.75
LOGO_SIZE = 0.185
TEXT_HEIGHT_MULTIPLIER = 0.35
ROW_X_OFFSET = 0.55
ROW_Y_OFFSET = 0.135
TEXT_CENTER_OFFSET = 0.35
SPACING = 0.02

def get_font_face(style="Calisto"):
    """Get font face based on style with fallback"""
    try:
        if style == "Calisto":
            return fonts.FontFace(filename="CALISTBI.TTF")
        elif style == "CreamCake":
            return fonts.FontFace(filename="DancingScript-Bold.ttf")
        return fonts.FontFace(filename="CALISTBI.TTF")
    except (FileNotFoundError, ValueError):
        return fonts.FontFace(family="Arial")

def calculate_layout_position(index, width, height, base_x, base_y):
    """Calculate position for entity based on index"""
    row = index // 10
    col = index % 10
    offset_x = (width + SPACING) * col
    offset_y = -(height + SPACING) * row
    
    if row % 2 != 0:
        offset_x += ROW_X_OFFSET
        offset_y += ROW_Y_OFFSET
        
    return base_x + offset_x, base_y + offset_y

def calculate_dimensions(extents):
    """Calculate dimensions and centers from extents"""
    if not extents:
        return None
    
    width = abs(extents.extmax[0] - extents.extmin[0])
    height = abs(extents.extmax[1] - extents.extmin[1])
    center_x = (extents.extmax[0] + extents.extmin[0]) / 2
    center_y = (extents.extmax[1] + extents.extmin[1]) / 2
    
    return {
        'width': width,
        'height': height,
        'center_x': center_x,
        'center_y': center_y,
        'text_height': min(width, height) * TEXT_HEIGHT_MULTIPLIER
    }

def process_path_vertices(text_path, offset_x=0, offset_y=0, distance=0.005, segments=1):
    """Process text path vertices and return either all vertices or create polylines with offset"""
    result = []
    for char in path.group_paths(path.single_paths([text_path])):
        for subpath in char:
            vertices = list(subpath.flattening(distance=distance, segments=segments))
            if vertices:
                if offset_x == 0 and offset_y == 0:
                    result.extend(vertices)
                else:
                    # Create translated vertices and close the path
                    translated = [(v[0] + offset_x, v[1] + offset_y) for v in vertices]
                    if translated[0] != translated[-1]:
                        translated.append(translated[0])
                    result.append(translated)
    return result

def add_text_to_entity(msp, text, center_x, center_y, text_height, style="Calisto"):
    """Add text to entity using text path"""
    font_face = get_font_face(style)
    
    # Create text path
    text_path = text2path.make_path_from_str(
        text,
        font_face,
        size=text_height
    )
    
    # Process vertices and add text
    all_vertices = process_path_vertices(text_path)
    if all_vertices:
        # Calculate text center and offset
        text_center_x = (max(v[0] for v in all_vertices) + min(v[0] for v in all_vertices)) / 2
        text_center_y = (max(v[1] for v in all_vertices) + min(v[1] for v in all_vertices)) / 2
        offset_x = center_x - text_center_x + TEXT_CENTER_OFFSET
        offset_y = center_y - text_center_y
        
        # Create polylines with offset
        for vertices in process_path_vertices(text_path, offset_x, offset_y):
            polyline = msp.add_polyline2d(vertices)
            polyline.dxf.color = 3

def copy_and_transform_entities(msp, entities, target_x, target_y, base_x, base_y):
    """Copy and transform a group of entities to new position"""
    copied_entities = []
    for entity in entities:
        try:
            copy = entity.copy()
            msp.add_entity(copy)
            copy.translate(target_x - base_x, target_y - base_y, 0)
            copied_entities.append(copy)
        except Exception as e:
            print(f"Warning: Could not copy entity {entity.dxftype()}: {str(e)}")
    return copied_entities

def insert_logo(doc, logo_file, entity_extents, scale_factor=SCALE_FACTOR):
    """Insert logo into the entity if logo file is provided"""
    # Skip if logo file is None or empty string
    if not logo_file:
        return
        
    try:
        msp = doc.modelspace()
        
        # Read the logo file
        logo_doc = ezdxf.readfile(logo_file)
        logo_msp = logo_doc.modelspace()
        logo_entities = logo_msp.query('CIRCLE LINE POLYLINE LWPOLYLINE')
        
        # Get logo extents
        logo_extents = bbox.extents(logo_msp)
        
        if not logo_extents or not entity_extents:
            print("Could not get extents for logo or entity")
            return
            
        # Calculate dimensions
        logo_width = abs(logo_extents.extmax[0] - logo_extents.extmin[0])
        logo_height = abs(logo_extents.extmax[1] - logo_extents.extmin[1])
        entity_width = abs(entity_extents.extmax[0] - entity_extents.extmin[0])
        
        # Calculate the center of the left circle (20% from the left edge)
        left_circle_x = entity_extents.extmin[0] + (entity_width * 0.125)
        entity_center_y = (entity_extents.extmin[1] + entity_extents.extmax[1]) / 2
        
        # Use a fixed scale factor relative to the entity width
        desired_logo_width = entity_width * LOGO_SIZE
        
        # Calculate scale factor based on the larger dimension of the logo
        logo_max_dimension = max(logo_width, logo_height)
        scale_factor = desired_logo_width / logo_max_dimension
        
        # Calculate logo center point (current position before transformation)
        logo_center_x = (logo_extents.extmin[0] + logo_extents.extmax[0]) / 2
        logo_center_y = (logo_extents.extmin[1] + logo_extents.extmax[1]) / 2
        
        # Calculate translation to move logo center to target position
        translation_x = left_circle_x - (logo_center_x * scale_factor)
        translation_y = entity_center_y - (logo_center_y * scale_factor)
        
        # Transform logo entities
        for entity in logo_entities:
            if hasattr(entity, 'transform'):
                # Scale the entity
                transform_matrix = Matrix44.scale(scale_factor)
                entity.transform(transform_matrix)
                # Move to target position
                entity.translate(translation_x, translation_y, 0)
                # Set appearance
                entity.dxf.color = 3
                entity.dxf.lineweight = 100
        
        # Import entities to base modelspace
        importer = Importer(logo_doc, doc)
        importer.import_modelspace()
        importer.finalize()
    except (FileNotFoundError, ezdxf.DXFError) as e:
        print(f"Error processing logo file: {e}")
        return

def duplicate_entities(source_file, target_file, logo_file, names):
    """
    Duplicate entities for each name and add empty templates to reach next multiple of 10.
    Empty templates will not include logos.
    If logo_file is None or empty string, no logos will be added to any template.
    """
    # Calculate padding needed to reach next multiple of 10
    total_names = len(names)
    next_multiple = ((total_names + 9) // 10) * 10
    empty_slots_needed = next_multiple - total_names
    
    # Create list of all positions (filled and empty)
    full_template_list = []
    current_row = 0
    current_col = 0
    
    # First, add all actual names
    for name in names:
        full_template_list.append({
            'position': (current_row, current_col),
            'name': name,
            'is_empty': False
        })
        current_col += 1
        if current_col == 10:
            current_col = 0
            current_row += 1
    
    # Then add empty templates to reach multiple of 10
    for _ in range(empty_slots_needed):
        full_template_list.append({
            'position': (current_row, current_col),
            'name': '',
            'is_empty': True
        })
        current_col += 1
        if current_col == 10:
            current_col = 0
            current_row += 1

    # Load and prepare source file
    doc = ezdxf.readfile(source_file)
    msp = doc.modelspace()
    original_entities = list(msp.query('LINE SPLINE POLYLINE'))
    
    # Get dimensions
    original_extents = bbox.extents(original_entities)
    if not original_extents:
        print("No entities found to duplicate")
        return
    
    dims = calculate_dimensions(original_extents)
    base_x = original_extents.extmin[0]
    base_y = original_extents.extmin[1]
    
    # Process original entity (first template)
    first_template = full_template_list[0]
    if not first_template['is_empty']:
        add_text_to_entity(msp, first_template['name'], dims['center_x'], dims['center_y'], dims['text_height'], "Calisto")
        # Only try to insert logo if logo_file is provided
        if logo_file:
            insert_logo(doc, logo_file, original_extents)
    
    # Process remaining templates
    for i, template in enumerate(full_template_list[1:], 1):
        target_x, target_y = calculate_layout_position(i, dims['width'], dims['height'], base_x, base_y)
        
        # Copy and transform entities (even for empty templates)
        current_entities = copy_and_transform_entities(msp, original_entities, target_x, target_y, base_x, base_y)
        
        # Add text and logo only for non-empty templates
        if not template['is_empty']:
            current_center_x = target_x + (dims['width'] / 2)
            current_center_y = target_y + (dims['height'] / 2)
            add_text_to_entity(msp, template['name'], current_center_x, current_center_y, dims['text_height'], "Calisto")
            
            # Only try to insert logo if logo_file is provided and we have entities
            if logo_file and current_entities:
                current_extents = bbox.extents(current_entities)
                insert_logo(doc, logo_file, current_extents)
    
    doc.saveas(target_file)
    print(f"Created {len(names)} templates with {empty_slots_needed} empty templates to reach {next_multiple} total templates")

if __name__ == "__main__":
    source_file = "test.dxf"
    target_file = "textpath_r12.dxf"
    logo_file = "logo/logo-untar.dxf"
    names = ["John", "Alice", "Bob", "Carol", "David", "Eve", "Frank", "Grace", "Henry", "Ivy", "Jack", "Kate", "Liam", "Mia", "Noah", "James"]
    duplicate_entities(source_file, target_file, logo_file, names)
