import os
import torch
from model import KinematicVelocityNet

def export_to_onnx(model_path='best_model.pt', onnx_path='model.onnx'):
    # 1. Load PyTorch model
    print("Loading PyTorch model...")
    model = KinematicVelocityNet()
    if os.path.exists(model_path):
        model.load_state_dict(torch.load(model_path, map_location='cpu'))
    model.eval()

    # 2. Export to ONNX
    print(f"Exporting to {onnx_path}...")
    dummy_input = torch.randn(1, 6, 100) # (batch, channels, seq_len)
    torch.onnx.export(
        model, 
        dummy_input, 
        onnx_path,
        export_params=True,
        opset_version=12,
        do_constant_folding=True,
        input_names=['imu_input'],
        output_names=['velocity_output'],
        dynamic_axes={'imu_input': {0: 'batch_size'}, 'velocity_output': {0: 'batch_size'}}
    )
    print(f"Successfully exported ONNX model to {onnx_path}!")

if __name__ == "__main__":
    export_to_onnx()
