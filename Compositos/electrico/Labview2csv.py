import os
import csv

def convert_to_csv(folder_path):
    # Iterate through all files in the given folder
    for filename in os.listdir(folder_path):
        input_filepath = os.path.join(folder_path, filename)
        
        # Skip directories
        if os.path.isdir(input_filepath):
            continue
            
        # Separate the file name and its extension
        name, ext = os.path.splitext(filename)
        
        # Check if the file has a .txt extension or no extension at all
        if ext.lower() in ['', '.txt']:
            output_filepath = os.path.join(folder_path, f"{name}.csv")
            
            try:
                # Open the input file to read and the output file to write
                with open(input_filepath, 'r', encoding='utf-8') as infile, \
                     open(output_filepath, 'w', newline='', encoding='utf-8') as outfile:
                    
                    # Read the tab-separated data
                    reader = csv.reader(infile, delimiter='\t')
                    # Write the comma-separated data
                    writer = csv.writer(outfile, delimiter=',')
                    
                    for row in reader:
                        writer.writerow(row)
                        
                print(f"Successfully converted: {filename} -> {name}.csv")
                
            except Exception as e:
                print(f"Error processing {filename}: {e}")

# --- Example Usage ---
# Replace 'your_folder_path_here' with the actual path to your directory
convert_to_csv(r'/home/martin/LBT/phd/Compositos/electrico/Archivos/PSS/')