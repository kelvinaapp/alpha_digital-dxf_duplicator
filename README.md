# DXF Duplicator

A web-based application that generates DXF files from Excel data and optionally includes logo placement. Built with Flask and modern web technologies.

## Features

- Excel to DXF conversion
- Optional logo placement
- Live preview of generated DXF files
- Progress tracking for file processing
- Interactive zoom controls for preview
- Responsive web interface

## Requirements

- Python 3.x
- Flask
- Pandas
- ezdxf
- matplotlib

## Installation

1. Clone the repository:
```bash
git clone [your-repository-url]
cd alpha_digital
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the application:
```bash
python app.py
```

2. Open your browser and navigate to `http://localhost:5000`

3. Upload Process:
   - Select an Excel file containing your data
   - Optionally enable logo placement and upload a DXF logo file
   - Click "Generate Documents" to process the files
   - Preview the generated DXF file
   - Download the final DXF file

## Project Structure

```
alpha_digital/
├── app.py              # Main Flask application
├── src/
│   └── dxf_manipulator.py  # DXF processing logic
├── templates/
│   └── index.html      # Web interface
├── static/
│   └── ...            # Static assets
├── uploads/           # Temporary file storage
└── requirements.txt   # Python dependencies
```

## Development

- The application uses Flask for the backend API
- Frontend is built with Bootstrap for responsive design
- File processing includes progress tracking
- Preview generation uses matplotlib
- DXF manipulation handled by ezdxf

## License

[Your License]

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request
