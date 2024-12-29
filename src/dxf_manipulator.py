import ezdxf
from ezdxf.addons import text2path
from ezdxf import bbox, path
from ezdxf.fonts import fonts
from ezdxf.addons.importer import Importer
from ezdxf.math import Matrix44
import pandas as pd
from src.progress_tracker import progress_tracker

# Constants
# logo size = 18.5%
LOGO_SIZE_RATIO = 0.185
ROW_X_OFFSET = 5.5
ROW_Y_OFFSET = 1.4
SPACING = 0.2

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
    
    if row > 0:
        row_multiplier = 1
        
        if row >= 2 :
            row_multiplier = row
            
        offset_y += ROW_Y_OFFSET * row_multiplier
            
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
        'center_y': center_y
    }

def calculate_text_height(text, width, height, style="Calisto", logo_exist=False):
    """
    Calculate optimal text height based on entity dimensions and text properties.
    
    Args:
        text (str): Text to be rendered
        width (float): Entity width
        height (float): Entity height
        style (str): Font style name
    
    Returns:
        float: Calculated text height
    """
    # Constants for size calculations
    TARGET_WIDTH_RATIO = 0.85
    
    if logo_exist:
        TARGET_WIDTH_RATIO = 0.7
    
    BASE_HEIGHT_RATIO = {
        'upper': 0.3,
        'lower': 0.35
    }
    LENGTH_THRESHOLDS = {
        'short': 6,
        'medium': 15
    }
    
    def get_text_bbox(text_path):
        """Extract bounding box coordinates from text path."""
        vertices = []
        for elem in text_path:
            if hasattr(elem, 'control_points'):
                for point in elem.control_points:
                    if hasattr(point, 'x') and hasattr(point, 'y'):
                        vertices.append((point.x, point.y))
            elif hasattr(elem, 'end'):
                if hasattr(elem.end, 'x') and hasattr(elem.end, 'y'):
                    vertices.append((elem.end.x, elem.end.y))
        
        if not vertices:
            return None
            
        x_coords = [v[0] for v in vertices]
        y_coords = [v[1] for v in vertices]
        return (min(x_coords), max(x_coords), min(y_coords), max(y_coords))
    
    # Create text path with test height
    text_path = text2path.make_path_from_str(text, get_font_face(style), size=1.0)
    bbox = get_text_bbox(text_path)
    
    if not bbox:
        return height * 0.25  # Fallback height
    
    # Calculate width ratio
    text_width = bbox[1] - bbox[0]
    if text_width == 0:
        return height * 0.25
    
    # Calculate base height
    base_ratio = BASE_HEIGHT_RATIO['upper' if text.isupper() else 'lower']
    base_height = height * base_ratio
    
    # Apply length-based adjustments
    text_len = len(text)
    if text_len <= LENGTH_THRESHOLDS['short']:
        max_height = base_height
    elif text_len <= LENGTH_THRESHOLDS['medium']:
        reduction = (text_len - LENGTH_THRESHOLDS['short']) * 0.01
        max_height = base_height * (1 - reduction)
    else:
        max_height = base_height * 0.7
    
    # Apply additional adjustments
    if ' ' in text:
        max_height *= 0.9
    if text.isupper() and text_len > 10:
        max_height *= 0.85
    
    # Calculate required height for target width
    required_height = (width * TARGET_WIDTH_RATIO) / text_width
    
    # Return final height with minimum constraint
    return max(min(required_height, max_height), height * 0.10)

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

def add_text_to_entity(msp, text, center_x, center_y, text_height, style="Calisto", logo_exist=False, TEXT_CENTER_OFFSET = 0):
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
        
        center_reposition=0
        
        # if len(text) < 6:
        #     center_reposition = 1
            
        if logo_exist:
            TEXT_CENTER_OFFSET = 4
            
        offset_x = center_x - text_center_x + TEXT_CENTER_OFFSET
        offset_y = center_y - text_center_y
        
        # Create polylines with offset
        for vertices in process_path_vertices(text_path, offset_x, offset_y, distance=0.001, segments=2):
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

def insert_logo(doc, logo_file, entity_extents, scale_factor=0.75):
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
        desired_logo_width = entity_width * LOGO_SIZE_RATIO
        
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

def duplicate_entities(source_file, target_file, logo_file, data_df):
    """
    Duplicate entities based on DataFrame containing Name, Quantity, and Category columns.
    Empty templates will be added between different categories and to reach next multiple of 10.
    If logo_file is None or empty string, no logos will be added to any template.
    
    Args:
        source_file: Source DXF file path
        target_file: Target DXF file path
        logo_file: Logo file path (optional)
        data_df: DataFrame with columns: Name, Quantity, Category
    """
    progress_tracker.update(0.15, 'Preparing template list...')
    
    # Create list of all positions (filled and empty)
    full_template_list = []
    current_row = 0
    current_col = 0
    last_category = None
    
    # Process each row in the DataFrame
    total_items = len(data_df)
    for idx, row in data_df.iterrows():
        
        name = row['Name']
        # Handle NaN values in Quantity column, default to 1
        quantity = 1 if pd.isna(row['Quantity']) else int(row['Quantity'])
        category = str(row['Category']) if not pd.isna(row['Category']) else ''
        
        # Add category separator if category changes
        if last_category is not None and category != last_category:
            full_template_list.append({
                'position': (current_row, current_col),
                'name': '',
                'is_empty': True
            })
            current_col += 1
            if current_col == 10:
                current_col = 0
                current_row += 1
        
        # Add entries based on quantity
        for _ in range(quantity):
            full_template_list.append({
                'position': (current_row, current_col),
                'name': name,
                'is_empty': False
            })
            current_col += 1
            if current_col == 10:
                current_col = 0
                current_row += 1
        
        last_category = category
    
    progress_tracker.update(0.25, 'Finalizing template list...')
    
    # Only pad the last category to reach multiple of 10
    if current_col > 0:  # Only if we're not already at the start of a new row
        empty_slots_needed = 10 - current_col
        for _ in range(empty_slots_needed):
            full_template_list.append({
                'position': (current_row, current_col),
                'name': '',
                'is_empty': True
            })
            current_col += 1

    progress_tracker.update(0.3, 'Loading source file...')
    
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
    
    logo_exist = bool(logo_file)
    
    progress_tracker.update(0.35, 'Processing first template...')
    
    # Process original entity (first template)
    first_template = full_template_list[0]
    if not first_template['is_empty']:
        dims['text_height'] = calculate_text_height(first_template['name'], dims['width'], dims['height'], "Calisto", logo_exist)
        # Only try to insert logo if logo_file is provided
        if logo_exist:
            insert_logo(doc, logo_file, original_extents)
        
        add_text_to_entity(msp, first_template['name'], dims['center_x'], dims['center_y'], dims['text_height'], "Calisto", logo_exist)
    
    # Process remaining templates
    total_templates = len(full_template_list[1:])
    for i, template in enumerate(full_template_list[1:], 1):
        progress = 0.35 + (0.45 * (i / total_templates))
        progress_tracker.update(progress, f'Processing template {i} of {total_templates + 1}')
        
        target_x, target_y = calculate_layout_position(i, dims['width'], dims['height'], base_x, base_y)
        
        # Copy and transform entities (even for empty templates)
        current_entities = copy_and_transform_entities(msp, original_entities, target_x, target_y, base_x, base_y)
        dims['text_height'] = calculate_text_height(template['name'], dims['width'], dims['height'], "Calisto", logo_exist)
        
        # Add text and logo only for non-empty templates
        if not template['is_empty']:
            current_center_x = target_x + (dims['width'] / 2)
            current_center_y = target_y + (dims['height'] / 2)
            
            # Only try to insert logo if logo_file is provided and we have entities
            if logo_exist and current_entities:
                current_extents = bbox.extents(current_entities)
                insert_logo(doc, logo_file, current_extents)
                
            add_text_to_entity(msp, template['name'], current_center_x, current_center_y, dims['text_height'], "Calisto", logo_exist)
    
    progress_tracker.update(0.8, 'Saving file...')
    doc.saveas(target_file)
    
    progress_tracker.update(0.85, 'Complete!')
    print(f"Created {len(data_df)} templates with {len(full_template_list) - len(data_df)} empty templates to reach {len(full_template_list)} total templates")

if __name__ == "__main__":
    source_file = "test.dxf"
    target_file = "textpath_r12.dxf"
    logo_file = "logo-untar.dxf"
    # logo_file = ""
    df = pd.read_excel("test-nama.xlsx", engine='openpyxl')
    data_df = df[['Name', 'Quantity', 'Category']]
    duplicate_entities(source_file, target_file, logo_file, data_df)
