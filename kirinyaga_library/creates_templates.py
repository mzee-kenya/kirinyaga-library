import os

# Create directories
os.makedirs('templates', exist_ok=True)
os.makedirs('static/css', exist_ok=True)
os.makedirs('static/js', exist_ok=True)
os.makedirs('static/imgs', exist_ok=True)

# Create empty CSS files
with open('static/css/style.css', 'w') as f:
    f.write('/* Style file will be created */')

with open('static/css/dashboard.css', 'w') as f:
    f.write('/* Dashboard styles */')

# Create empty JS file
with open('static/js/script.js', 'w') as f:
    f.write('// JavaScript file')

print("Directories and empty files created successfully!")
print("Now copy the template content from above into each file.")