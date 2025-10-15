# IQ Tester App

An intuitive and responsive web application designed to assess IQ using the authentic Ravens IQ test. The app offers a seamless user experience and dynamic certificate generation with instant results.

https://github.com/user-attachments/assets/9a56ad14-4c67-4404-a3ad-8dfb5b06cc1d

## Features

- **Responsive Design**: The app is optimized for all devices, ensuring a smooth experience on desktops, tablets, and mobiles.
- **User-friendly Navigation**: Intuitive progress bar and easy navigation between questions to modify answers.
- **Dynamic Certificate Generation**: Generates personalized certificates with the user's name, score, and a unique serial number.
- **Instant Results**: View your IQ test results immediately after completion with a downloadable certificate.
- **Permanent Shareable Links**: Each result gets a permanent shareable link with certificate.
- **Social Sharing**: Result pages are equipped with social share buttons (optional).
- **Authentic Ravens IQ Test**: Uses genuine Ravens test methods and age-specific score calculations.

## Screenshots

![Homepage](https://github.com/user-attachments/assets/0e48127d-2518-4140-b3c4-8737234161f5)
![Question](https://github.com/user-attachments/assets/2c050b16-837b-47ff-9301-5b04e59ddc60)
![Certificate](https://github.com/user-attachments/assets/b603609f-f418-4d23-945b-d291b6663741)

## Technologies Used

- **Backend**: Python with Bottle web framework
- **Database**: SQLite
- **Frontend**: HTML, CSS, JavaScript
- **Certificate Generation**: Pillow (PIL)

## Prerequisites

Before you begin, ensure you have the following installed on your system:

- **Python 3.7+**: [Download Python](https://www.python.org/downloads/)
- **pip**: Python package installer (usually comes with Python)

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <repository-url>
cd <repository-directory>
```

### 2. Install Dependencies

Install the required Python packages using pip:

```bash
pip install -r requirements.txt
```

This will install:
- `bottle` - Lightweight web framework
- `python-dotenv` - Environment variable management
- `pillow` - Image processing for certificate generation

### 3. Configure Environment Variables

Copy the environment template file and configure it:

```bash
cp .env.template .env
```

Edit the `.env` file with your preferred settings:

```bash
# Server configuration
SERVER_HOST=0.0.0.0        # Use 0.0.0.0 to allow external access, or 127.0.0.1 for localhost only
SERVER_PORT=8080           # Port number (use 80 for production, 8080 for development)

# Optional: Add social sharing functionality (leave empty to disable)
SHARETHIS_ADDIN=

# Optional: Contact email for support
ADMIN_CONTACT=your-email@example.com
```

**Note**: Default settings work fine for local development. You can start with the template as-is.

### 4. Run the Application

Start the application using one of these methods:

#### Option A: Using the start script (Recommended)

```bash
python src/start_local.py
```

#### Option B: Using the server directly

```bash
cd src
python server.py
```

### 5. Access the Application

Open your web browser and navigate to:

```
http://localhost:8080
```

If you changed the `SERVER_PORT` in your `.env` file, use that port instead.

## Project Structure

```
.
├── src/
│   ├── webroot/           # Frontend files (HTML, CSS, JS, images)
│   │   ├── index.html     # Main application page
│   │   └── assets/        # Static assets
│   ├── cert_assets/       # Certificate template and fonts
│   ├── server.py          # Main server application
│   ├── tester.py          # IQ test logic and certificate generation
│   ├── storage.py         # Database operations
│   ├── util.py            # Utility functions
│   ├── start_local.py     # Local server starter
│   └── result_template.html  # Result page template
├── requirements.txt       # Python dependencies
├── .env.template          # Environment variables template
└── README.md             # This file
```

## Usage

1. **Start the Test**: Click "Start now" on the homepage
2. **Read Instructions**: Review the test instructions and click "Begin"
3. **Complete Questions**: Answer all 60 questions within 20 minutes
4. **Enter Details**: Provide your age and name when prompted
5. **View Results**: Your results will be displayed automatically with a downloadable certificate

## Database

The application uses SQLite for storing test results. The database file (`tester.db`) will be created automatically in the `src/` directory on first run.

**Database Schema**:
- `results` table: Stores test results with ID, score, age, timestamp, user name, and result tier

## Troubleshooting

### Port Already in Use

If you see an error that the port is already in use:

1. Change the `SERVER_PORT` in your `.env` file to a different port (e.g., 8081, 8082)
2. Or stop the process using that port

### Missing Dependencies

If you encounter import errors:

```bash
pip install -r requirements.txt --upgrade
```

### Permission Issues

If running on port 80 requires elevated privileges:

- On Linux/Mac: Use `sudo python src/start_local.py`
- Or change `SERVER_PORT` to a port above 1024 (e.g., 8080)

### Database Issues

If you encounter database errors:

1. Delete the `src/tester.db` file
2. Restart the application (database will be recreated)

## Development

### Running in Development Mode

For development, use:

```bash
cd src
python start_local.py
```

The server will automatically reload when you make changes to the code (depending on your environment).

### Testing

Test the IQ calculation logic:

```bash
cd src
python tester.py
```

## Production Deployment

For production deployment:

1. Set `SERVER_HOST=0.0.0.0` and `SERVER_PORT=80` in `.env`
2. Consider using a production WSGI server like Gunicorn or uWSGI
3. Set up a reverse proxy (nginx or Apache)
4. Enable HTTPS with SSL certificates
5. Configure firewall rules
6. Set up automated backups for the database

Example with Gunicorn:

```bash
pip install gunicorn
cd src
gunicorn -w 4 -b 0.0.0.0:8080 bottle_app:app
```

## Support

For issues or questions:
- Check the troubleshooting section above
- Contact the administrator at the email specified in your `.env` file
