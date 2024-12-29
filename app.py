from flask import Flask, render_template, request, send_file, jsonify
import os
from werkzeug.utils import secure_filename
import pandas as pd
from src.dxf_manipulator import duplicate_entities
import ezdxf
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
import matplotlib.pyplot as plt
import base64
from io import BytesIO
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
import logging
from logging.handlers import RotatingFileHandler
import tempfile
from functools import wraps
import time
from src.progress_tracker import progress_tracker

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=3)
logger.addHandler(handler)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['CACHE_TYPE'] = 'simple'
app.config['CACHE_DEFAULT_TIMEOUT'] = 300

# Initialize extensions
cache = Cache(app)
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["1000 per day", "200 per hour"],
    storage_uri="memory://"
)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'dxf', 'xlsx', 'xls'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def timing_decorator(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        start = time.time()
        result = f(*args, **kwargs)
        end = time.time()
        logger.info(f'Function {f.__name__} took {end-start:.2f} seconds')
        return result
    return wrap

@timing_decorator
def dxf_to_image(doc):
    # progress_tracker.update(0.8, 'Generating preview image...')
    tmp_file = None
    
    try:
        logger.info("Starting DXF to image conversion")
        msp = doc.modelspace()
        
        # Create figure with optimal settings
        fig = plt.figure(figsize=(12, 12), dpi=300)
        ax = plt.axes([0, 0, 1, 1])
        
        logger.info("Setting up rendering context")
        # Configure rendering context
        ctx = RenderContext(doc)
        ctx.current_color = '#000000'
        ctx.current_lineweight = 0.5
        
        # Configure backend
        out = MatplotlibBackend(ax)
        out.draw_lineweight = False
        
        logger.info("Drawing layout")
        # Draw the layout
        Frontend(ctx, out).draw_layout(msp, finalize=True)
        
        # Configure plot
        ax.set_axis_off()
        plt.margins(0, 0)
        
        progress_tracker.update(0.9, 'Saving image...')
        
        # Create a BytesIO buffer for the image
        img_buffer = BytesIO()
        
        try:
            logger.info("Saving to memory buffer")
            # Save directly to memory buffer
            plt.savefig(
                img_buffer,
                format='png',
                bbox_inches='tight',
                pad_inches=0,
                dpi=300,
                facecolor='white',
                transparent=False
            )
            
            # Clean up matplotlib resources
            plt.close(fig)
            
            # Get the image data
            img_buffer.seek(0)
            img_base64 = base64.b64encode(img_buffer.getvalue()).decode()
            
            progress_tracker.update(1.0, 'Complete!')
            logger.info("Image generation completed successfully")
            return img_base64
            
        except Exception as e:
            logger.error(f"Error saving/encoding image: {str(e)}")
            raise Exception(f"Failed to save or encode image: {str(e)}")
        finally:
            # Clean up the buffer
            img_buffer.close()
            
    except Exception as e:
        logger.error(f"Error in dxf_to_image: {str(e)}")
        progress_tracker.update(1.0, 'Error occurred during image generation')
        raise Exception(f"Failed to generate image from DXF: {str(e)}")
    finally:
        # Ensure matplotlib figure is closed
        plt.close('all')

@timing_decorator
def process_files(excel_path, logo_path):
    try:
        # Read Excel file in a memory-efficient way
        logger.info(f"Reading Excel file: {excel_path}")
        df = pd.read_excel(excel_path, engine='openpyxl')
        
        # Ensure required columns exist
        required_columns = ['Name', 'Quantity', 'Category']
        for col in required_columns:
            if col not in df.columns:
                df[col] = ''  # Add empty column if it doesn't exist
                if col == 'Quantity':
                    df[col] = 1  # Default quantity to 1
                if col == 'Category':
                    df[col] = 'Default'  # Default category
        
        data_df = df[required_columns]
        logger.info(f"Found {len(data_df)} entries in Excel file")
        
        template_path = 'public/dxf_template/template.dxf'
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], 'output.dxf')
        
        if logo_path:
            logger.info("Processing with logo")
            duplicate_entities(template_path, output_path, logo_path, data_df)
        else:
            logger.info("Processing without logo")
            duplicate_entities(template_path, output_path, None, data_df)
            
        logger.info(f"Successfully created output file: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error in process_files: {str(e)}")
        raise

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/progress')
@limiter.exempt
def get_progress():
    try:
        return jsonify({
            'progress': progress_tracker._progress,
            'status': progress_tracker._status,
            'complete': progress_tracker._complete
        })
    except Exception as e:
        logger.error(f"Error in progress endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/upload', methods=['POST'])
@limiter.limit("10 per minute")
def upload_file():
    try:
        logger.info("Starting file upload process")
        progress_tracker.reset()
        
        # Check if files are present in request
        if 'excelFile' not in request.files:
            logger.error("No excel file part in the request")
            return jsonify({'error': 'No excel file part'}), 400
            
        excel_file = request.files['excelFile']
        if excel_file.filename == '':
            logger.error("No excel file selected")
            return jsonify({'error': 'No excel file selected'}), 400

        if not allowed_file(excel_file.filename):
            logger.error(f"Invalid file type for excel file: {excel_file.filename}")
            return jsonify({'error': 'Invalid file type. Allowed types are: ' + ', '.join(ALLOWED_EXTENSIONS)}), 400

        progress_tracker.update(0.05, 'Processing uploaded files...')
        logger.info(f"Processing excel file: {excel_file.filename}")

        # Handle optional logo file
        logo_file = None
        logo_path = None
        if 'logoFile' in request.files:
            logo_file = request.files['logoFile']
            if logo_file.filename != '':
                if not allowed_file(logo_file.filename):
                    logger.error(f"Invalid file type for logo file: {logo_file.filename}")
                    return jsonify({'error': 'Invalid logo file type'}), 400
                logger.info(f"Processing logo file: {logo_file.filename}")

        progress_tracker.update(0.1, 'Saving files...')

        # Ensure upload directory exists
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
            logger.info(f"Created upload directory: {app.config['UPLOAD_FOLDER']}")

        # Save files with secure filenames
        try:
            excel_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(excel_file.filename))
            excel_file.save(excel_path)
            logger.info(f"Saved excel file to: {excel_path}")

            if logo_file and logo_file.filename != '':
                logo_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(logo_file.filename))
                logo_file.save(logo_path)
                logger.info(f"Saved logo file to: {logo_path}")
        except Exception as e:
            logger.error(f"Error saving files: {str(e)}")
            progress_tracker.update(1.0, f'Error: {str(e)}')
            return jsonify({'error': f'Error saving files: {str(e)}'}), 500

        progress_tracker.update(0.15, 'Processing files...')

        try:
            # Process the files and generate preview
            output_path = process_files(excel_path, logo_path)
            logger.info(f"Generated output file at: {output_path}")
            
            progress_tracker.update(0.85, 'Generating preview...')
            
            # Generate preview image
            doc = ezdxf.readfile(output_path)
            preview_base64 = dxf_to_image(doc)
            
            progress_tracker.update(1.0, 'Complete!')
            logger.info("File processing completed successfully")
            
            # Get the output filename
            output_filename = os.path.basename(output_path)
            
            return jsonify({
                'preview': preview_base64,
                'message': 'Files processed successfully',
                'filename': output_filename,
                'progress': 1.0,
                'complete': True
            })
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error processing files: {error_msg}")
            progress_tracker.update(1.0, f'Error: {error_msg}')
            return jsonify({'error': f'Error processing files: {error_msg}'}), 500
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Unexpected error in upload_file: {error_msg}")
        progress_tracker.update(1.0, f'Error: {error_msg}')
        return jsonify({'error': f'Unexpected error: {error_msg}'}), 500

@app.route('/download/<filename>')
def download_file(filename):
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
            
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/x-dxf'
        )
    except Exception as e:
        return jsonify({'error': f'Error downloading file: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True)
