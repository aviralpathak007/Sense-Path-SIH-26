import os
import torch
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from dataset import IOVNBDDataset
from model import KinematicVelocityNet, get_device

def evaluate_model(test_csv, model_path='best_model.pt', output_img='drift_benchmark.png'):
    device = get_device()
    print(f"Running evaluation on: {device}")
    
    # Load dataset
    dataset = IOVNBDDataset(test_csv, is_train=False)
    
    # Load model
    model = KinematicVelocityNet().to(device)
    if os.path.exists(model_path):
        model.load_state_dict(torch.load(model_path, map_location=device))
        model.eval()
    else:
        print(f"Warning: {model_path} not found. Using untrained model.")
        
    gt_velocity = []
    ai_predicted = []
    raw_integration = []
    
    # For double integration naive approach
    current_vel = 0.0
    
    with torch.no_grad():
        for i in range(len(dataset)):
            x, y = dataset[i]
            x_batch = x.unsqueeze(0).to(device)
            
            # AI Prediction
            pred = model(x_batch).item()
            ai_predicted.append(pred)
            gt_velocity.append(y.item())
            
            # Naive single integration from acceleration (forward axis - assuming acc_y is forward)
            # x shape is (6, 100), forward accel is index 1
            acc_y = x[1, :].numpy()
            
            # dt = 0.01 for 100Hz
            dt = 0.01 
            for a in acc_y:
                # Denormalize accel for naive approach roughly (placeholder values for Z-score)
                # In real scenario, we'd use the raw accel values
                real_a = a * 9.81 / 5.0 # Rough approx
                current_vel += real_a * dt
                
            raw_integration.append(current_vel)

    # Plotting
    plt.figure(figsize=(12, 6))
    plt.plot(gt_velocity, label='Ground Truth Velocity', color='green', linewidth=2)
    plt.plot(ai_predicted, label='AI-Predicted Velocity', color='blue', linewidth=2, linestyle='--')
    plt.plot(raw_integration, label='Raw Double-Integration (Drift)', color='red', linewidth=1.5, alpha=0.7)
    
    plt.title('Kinematics Velocity Estimator: AI vs Classical Dead Reckoning')
    plt.xlabel('Time Windows (0.5s intervals)')
    plt.ylabel('Forward Velocity (m/s)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.savefig(output_img, dpi=300, bbox_inches='tight')
    print(f"Evaluation complete. Saved benchmark plot to {output_img}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--test_csv', type=str, default='test_iovnbd.csv')
    args = parser.parse_args()
    
    if os.path.exists(args.test_csv):
        evaluate_model(args.test_csv)
    else:
        print(f"Please provide a valid IO-VNBD test CSV file.")
