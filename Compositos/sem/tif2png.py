import os
from PIL import Image

# Set your folders here
input_folder = "/home/martin/Downloads/"
output_folder = "/home/martin/LBT/phd/Compositos/sem/jul 26/"
target_format = "png" # change to "png" if you prefer

os.makedirs(output_folder, exist_ok=True)

for filename in os.listdir(input_folder):
    if filename.lower().endswith((".tif", ".tiff")):
        input_path = os.path.join(input_folder, filename)
        
        # Replace extension for the output file
        base_name = os.path.splitext(filename)[0]
        output_name = f"{base_name}.{target_format[:3]}"
        output_path = os.path.join(output_folder, output_name)
        
        try:
            with Image.open(input_path) as img:
                # Convert to RGB to avoid issues with 16-bit/CMYK TIFs
                rgb_im = img.convert("RGB")
                
                if target_format == "jpeg":
                    rgb_im.save(output_path, "JPEG", quality=85)
                else:
                    rgb_im.save(output_path, "PNG")
                    
            print(f"Converted: {filename}")
        except Exception as e:
            print(f"Failed to convert {filename}: {e}")

print("Batch conversion complete.")