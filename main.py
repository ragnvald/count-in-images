import tkinter as tk
from tkinter import filedialog, ttk
from PIL import Image, ImageTk, ExifTags
import sqlite3
import os
import configparser
import geopandas as gpd
from shapely.geometry import Point
from PIL import ImageDraw

# Global variable to store the click data
click_data = []
MAX_IMAGE_SIZE = 800
current_longitude = None
current_latitude = None
selected_species = None



def read_config():
    config = configparser.ConfigParser()
    config.read('config.ini')
    return config['Species']['list'].split(',')

def setup_database():
    conn = sqlite3.connect('annotations.db')
    # Database setup code remains the same...
    conn.close()

def load_images(folder):
    images = []
    for file in os.listdir(folder):
        if file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
            images.append(os.path.join(folder, file))
    return images

def get_exif_data(image_path):
    img = Image.open(image_path)
    exif_data = img._getexif()
    if not exif_data:
        return None, None
    for tag, value in exif_data.items():
        decoded = ExifTags.TAGS.get(tag, tag)
        if decoded == 'GPSInfo':
            gps_data = value
            return parse_gps_data(gps_data)
    return None, None

def parse_gps_data(gps_data):
    def dms_to_decimal(degrees, minutes, seconds, direction):
        decimal = float(degrees) + float(minutes)/60 + float(seconds)/3600
        if direction in ['S', 'W']:
            decimal = -decimal
        return decimal

    lat_dms = gps_data[2]
    lat_direction = gps_data[1]
    latitude = dms_to_decimal(lat_dms[0], lat_dms[1], lat_dms[2], lat_direction)

    lon_dms = gps_data[4]
    lon_direction = gps_data[3]
    longitude = dms_to_decimal(lon_dms[0], lon_dms[1], lon_dms[2], lon_direction)

    return latitude, longitude


def update_details_panel(image_path):
    filename = os.path.basename(image_path)
    longitude, latitude = get_exif_data(image_path)

    # Truncate the longitude and latitude to 5 decimal places for display
    longitude = f"{float(longitude):.5f}" if longitude else "N/A"
    latitude = f"{float(latitude):.5f}" if latitude else "N/A"

    details_text.set(f"Filename: {filename}\nLon: {longitude}\nLat: {latitude}")

def resize_image(event=None):
    if event.width > 0 and event.height > 0:
        update_image(images[image_index])

def on_image_click(event):
    # Calculate the actual coordinates on the original image
    ratio = min(MAX_IMAGE_SIZE / original_img.width, MAX_IMAGE_SIZE / original_img.height)
    actual_x = int(event.x / ratio)
    actual_y = int(event.y / ratio)
    global click_data, selected_species
    click_data.append({
        "image_name": os.path.basename(images[image_index]),
        "longitude": current_longitude,
        "latitude": current_latitude,
        "recorded_x": actual_x,
        "recorded_y": actual_y,
        "species": selected_species.get()  # Record the selected species
    })
    write_to_geopackage()
    update_image(images[image_index])


def write_to_geopackage():
    output_file = "data_out/wildlife.gpkg"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Create a GeoSeries from the longitude and latitude
    geometry = [Point(row['longitude'], row['latitude']) for row in click_data]
    df = gpd.GeoDataFrame(click_data, geometry=geometry)

    if not df.empty:
        df.to_file(output_file, layer='tbl_registrations', driver="GPKG")
    else:
        print("No data to save.")


def update_image(image_path):
    global current_longitude, current_latitude
    longitude, latitude = get_exif_data(image_path)
    current_longitude = longitude
    current_latitude = latitude
    global original_img
    original_img = Image.open(image_path)
    img = original_img.copy()

    # Calculate the resizing ratio and resize the image first
    ratio = min(MAX_IMAGE_SIZE / img.width, MAX_IMAGE_SIZE / img.height)
    new_width = int(img.width * ratio)
    new_height = int(img.height * ratio)
    img = img.resize((new_width, new_height))

    draw = ImageDraw.Draw(img)

    # Draw red dots for each registration on the resized image
    for data in click_data:
        if data['image_name'] == os.path.basename(image_path):
            dot_x = int(data['recorded_x'] * ratio)
            dot_y = int(data['recorded_y'] * ratio)
            line_length = 10  # Length of each line of the crosshair
            # Horizontal line
            draw.line([(dot_x - line_length, dot_y), (dot_x + line_length, dot_y)], fill='red', width=1)
            # Vertical line
            draw.line([(dot_x, dot_y - line_length), (dot_x, dot_y + line_length)], fill='red', width=1)

    photo = ImageTk.PhotoImage(img)
    image_label.config(image=photo)
    image_label.image = photo
    update_details_panel(image_path)


def next_image():
    global image_index
    image_index += 1
    if image_index >= len(images):
        image_index = 0  # Loop back to the first image
    update_image(images[image_index])


def prev_image():
    global image_index
    image_index -= 1
    if image_index < 0:
        image_index = len(images) - 1  # Loop to the last image
    update_image(images[image_index])


def init_main_window():
    global image_label, images, image_index, details_text, original_img
    root = tk.Tk()
    root.title("Wildlife Image Annotation Tool")

    # Main frame which holds both left and right frames
    main_frame = ttk.Frame(root)
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Frame for image display
    image_frame = ttk.Frame(main_frame)
    image_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Image label for displaying the image
    image_label = tk.Label(image_frame)
    image_label.pack(expand=True)
    image_label.bind("<Button-1>", on_image_click)  # Bind left mouse click here

    # Frame for navigation buttons
    nav_frame = ttk.Frame(image_frame)
    nav_frame.pack(side=tk.BOTTOM, fill=tk.X)
    ttk.Button(nav_frame, text="Previous", command=prev_image).pack(side=tk.LEFT)
    ttk.Button(nav_frame, text="Next", command=next_image).pack(side=tk.RIGHT)

    # Right frame for displaying details
    right_frame = ttk.Frame(main_frame, width=200)
    right_frame.pack(side=tk.RIGHT, fill=tk.Y, expand=False)
    right_frame.pack_propagate(False)

    # Create a dropdown for species selection
    global selected_species
    selected_species = tk.StringVar()
    species_dropdown = ttk.Combobox(right_frame, textvariable=selected_species, values=read_config())
    species_dropdown.pack()

    # Label for displaying image details
    details_text = tk.StringVar()
    details_label = ttk.Label(right_frame, textvariable=details_text, justify=tk.LEFT)
    details_label.pack()

    # Load images and set the initial image
    images = load_images('data_in')
    image_index = 0
    if images:
        update_image(images[image_index])

    root.mainloop()


species_list = read_config()

setup_database()

init_main_window()
