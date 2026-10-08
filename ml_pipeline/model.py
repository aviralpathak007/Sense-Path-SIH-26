import torch
import torch.nn as nn

class KinematicVelocityNet(nn.Module):
    def __init__(self, in_channels=6, window_size=100):
        super(KinematicVelocityNet, self).__init__()
        
        # 1D CNN to filter out high-frequency noise
        self.cnn = nn.Sequential(
            nn.Conv1d(in_channels, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool1d(2),
            nn.Conv1d(32, 64, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool1d(2)
        )
        
        # Calculate sequence length after pooling
        cnn_out_len = window_size // 4
        
        # Bidirectional GRU to capture temporal dynamics
        self.gru = nn.GRU(
            input_size=64, 
            hidden_size=64, 
            num_layers=2, 
            batch_first=True, 
            bidirectional=True
        )
        
        # Dense regression head for predicting forward velocity (m/s)
        self.fc = nn.Sequential(
            nn.Linear(64 * 2, 32), # *2 because of bidirectional
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 1)
        )

    def forward(self, x):
        # x shape: (batch, in_channels, seq_len)
        features = self.cnn(x)
        
        # Transpose for GRU: (batch, seq_len, channels)
        features = features.permute(0, 2, 1)
        
        # GRU output: (batch, seq_len, hidden_size * num_directions)
        gru_out, _ = self.gru(features)
        
        # Take the last time step output from GRU
        last_out = gru_out[:, -1, :]
        
        # Regress to continuous velocity
        vel_pred = self.fc(last_out)
        
        return vel_pred.squeeze()

def get_device():
    if torch.backends.mps.is_available():
        return torch.device("mps")
    elif torch.cuda.is_available():
        return torch.device("cuda")
    else:
        return torch.device("cpu")
