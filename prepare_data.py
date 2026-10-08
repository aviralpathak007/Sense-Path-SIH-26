import pandas as pd
import os
import urllib.request
import urllib.parse

def download_lfs_if_needed(local_path):
    # If file is a Git LFS pointer (typically < 300 bytes), download the real file
    if os.path.exists(local_path) and os.path.getsize(local_path) < 1000:
        print(f"{local_path} looks like a Git LFS pointer. Downloading the real file...")
        
        # Construct GitHub raw URL
        # We replace the local root "IO-VNBD-master" with the raw URL prefix
        repo_prefix = "IO-VNBD-master/"
        if local_path.startswith(repo_prefix):
            rel_path = local_path[len(repo_prefix):]
            url = f"https://github.com/onyekpeu/IO-VNBD/raw/master/{urllib.parse.quote(rel_path)}"
            urllib.request.urlretrieve(url, local_path)
            print(f"Successfully downloaded real file for {local_path}!")

def merge_and_save(smartphone_csv, vehicle_csv, output_name):
    # Ensure real files are downloaded if they are just LFS pointers
    download_lfs_if_needed(smartphone_csv)
    download_lfs_if_needed(vehicle_csv)
    
    print(f"Merging {smartphone_csv} and {vehicle_csv}...")
    
    # Load the synchronized CSVs (handling special degree/squared characters)
    df_s = pd.read_csv(smartphone_csv, encoding='latin1', on_bad_lines='skip')
    df_v = pd.read_csv(vehicle_csv, encoding='latin1', on_bad_lines='skip')
    
    # S-M.csv indices: 9(AccX), 10(AccY), 11(AccZ), 15(GyroYaw), 16(GyroPitch), 17(GyroRoll)
    # V-M.csv indices: 4(Velocity km/hr)
    merged_df = pd.DataFrame({
        'acc_x': df_s.iloc[:, 9],
        'acc_y': df_s.iloc[:, 10],
        'acc_z': df_s.iloc[:, 11],
        'gyro_x': df_s.iloc[:, 17], # Roll
        'gyro_y': df_s.iloc[:, 16], # Pitch
        'gyro_z': df_s.iloc[:, 15], # Yaw
        'velocity_forward': df_v.iloc[:, 4] / 3.6 # Convert km/h to m/s
    })
    
    merged_df.to_csv(output_name, index=False)
    print(f"Saved formatted dataset to {output_name}")

if __name__ == "__main__":
    # Ensure the data directory exists
    os.makedirs("data", exist_ok=True)
    
    # Using the local path in the Sense-Path directory
    base_path = "IO-VNBD-master/Synchronised V abd S datasets/Categorised IOVNB Dataset"
    
    # Generate Train Set (Driver B)
    merge_and_save(f"{base_path}/M (Driver B)/S-M.csv", 
                   f"{base_path}/M (Driver B)/V-M.csv", 
                   "data/train_iovnbd.csv")
                   
    # Generate Val Set (Driver E - Vfa01)
    merge_and_save(f"{base_path}/Vf (Driver E)/V-Vfa01/S-Vfa01.csv", 
                   f"{base_path}/Vf (Driver E)/V-Vfa01/V-Vfa01.csv", 
                   "data/val_iovnbd.csv")
                   
    # Generate Test Set (Driver E - Vta03)
    merge_and_save(f"{base_path}/Vta (Driver E)/Vta03/S-Vta3.csv", 
                   f"{base_path}/Vta (Driver E)/Vta03/V-vta3.csv", 
                   "data/test_iovnbd.csv")
