import pandas as pd
import numpy as np
import torch
from torch.utils.data import Dataset

class IOVNBDDataset(Dataset):
    def __init__(self, csv_file, window_size=100, overlap=50, is_train=True):
        """
        Parses IO-VNBD format CSV.
        Expected columns: 'acc_x', 'acc_y', 'acc_z', 'gyro_x', 'gyro_y', 'gyro_z', 'velocity_forward'
        """
        self.window_size = window_size
        self.overlap = overlap
        
        # Load the dataset
        df = pd.read_csv(csv_file)
        
        # Extract features (6-axis IMU) and labels (forward velocity)
        # IO-VNBD datasets often have different column names, we assume standard ones here
        imu_cols = ['acc_x', 'acc_y', 'acc_z', 'gyro_x', 'gyro_y', 'gyro_z']
        
        # Normalize IMU data (Z-score normalization)
        self.imu_data = df[imu_cols].values.astype(np.float32)
        mean = np.mean(self.imu_data, axis=0)
        std = np.std(self.imu_data, axis=0) + 1e-8
        self.imu_data = (self.imu_data - mean) / std
        
        # Assuming ground-truth velocity is provided in 'velocity_forward'
        if 'velocity_forward' in df.columns:
            self.velocity = df['velocity_forward'].values.astype(np.float32)
        else:
            # Fallback if testing on data without GT
            self.velocity = np.zeros(len(df), dtype=np.float32)
            
        self.windows = self._create_windows()

    def _create_windows(self):
        step_size = self.window_size - self.overlap
        num_windows = (len(self.imu_data) - self.window_size) // step_size + 1
        windows = []
        for i in range(num_windows):
            start = i * step_size
            end = start + self.window_size
            windows.append((start, end))
        return windows

    def __len__(self):
        return len(self.windows)

    def __getitem__(self, idx):
        start, end = self.windows[idx]
        
        # x shape: (window_size, 6) -> transpose to (6, window_size) for CNN 1D
        x = self.imu_data[start:end]
        x = np.transpose(x, (1, 0))
        
        # Target is the velocity at the end of the window
        y = self.velocity[end - 1]
        
        return torch.tensor(x, dtype=torch.float32), torch.tensor(y, dtype=torch.float32)
