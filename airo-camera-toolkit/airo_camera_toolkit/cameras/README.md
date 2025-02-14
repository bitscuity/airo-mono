
# Cameras
This subpackage contains implementations of the camera interface for the cameras we have at AIRO.

## 1. Installation
Implementations usually require the installation of SDKs, drivers etc. to communicate with the camera.
This information can be found in `READMEs` for each camera:
* [ZED Installation](zed_installation.md)

## 2. Testing your hardware installation
Furthermore, there is code for testing the hardware implementations.
But since this requires attaching a physical camera, these are 'user tests' which should be done manually by developers/users.
Each camera implementation can be run as a script and will execute the relevant tests, providing instructions on what to look out for.

For example, to test your ZED installation:
```
conda activate airo-mono
python3 zed2i.py
```