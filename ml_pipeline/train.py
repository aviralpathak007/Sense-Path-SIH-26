import os
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from dataset import IOVNBDDataset
from model import KinematicVelocityNet, get_device

def train_model(train_csv, val_csv, epochs=50, batch_size=32, patience=5, save_path='best_model.pt'):
    device = get_device()
    print(f"Using device: {device}")
    
    # Create datasets and dataloaders
    train_dataset = IOVNBDDataset(train_csv, is_train=True)
    val_dataset = IOVNBDDataset(val_csv, is_train=False)
    
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
    
    model = KinematicVelocityNet().to(device)
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=1e-3)
    
    best_val_loss = float('inf')
    patience_counter = 0
    
    for epoch in range(epochs):
        model.train()
        train_loss = 0.0
        for x_batch, y_batch in train_loader:
            x_batch, y_batch = x_batch.to(device), y_batch.to(device)
            
            optimizer.zero_grad()
            outputs = model(x_batch)
            loss = criterion(outputs, y_batch)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item() * x_batch.size(0)
            
        train_loss /= len(train_loader.dataset)
        
        # Validation
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for x_batch, y_batch in val_loader:
                x_batch, y_batch = x_batch.to(device), y_batch.to(device)
                outputs = model(x_batch)
                loss = criterion(outputs, y_batch)
                val_loss += loss.item() * x_batch.size(0)
                
        val_loss /= len(val_loader.dataset)
        
        print(f"Epoch {epoch+1}/{epochs} - Train Loss: {train_loss:.4f} - Val Loss: {val_loss:.4f}")
        
        # Early Stopping
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            torch.save(model.state_dict(), save_path)
            print(f"Saved new best model with Val Loss: {best_val_loss:.4f}")
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"Early stopping triggered at epoch {epoch+1}")
                break

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--train_csv', type=str, default='train_iovnbd.csv')
    parser.add_argument('--val_csv', type=str, default='val_iovnbd.csv')
    args = parser.parse_args()
    
    # Only run if dummy or real files exist to avoid error
    if os.path.exists(args.train_csv) and os.path.exists(args.val_csv):
        train_model(args.train_csv, args.val_csv)
    else:
        print(f"Please provide valid paths to the IO-VNBD dataset CSV files.")
