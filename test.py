#%%
import matplotlib.pyplot as plt
# from mpl_toolkits.mplot3d import Axes3D
import numpy as np

# Create figure and 3D axis
fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')

# Create high resolution cloth
x = np.linspace(0, 10, 200)
y = np.linspace(0, 10, 200)
X, Y = np.meshgrid(x, y)
Z = np.sin(X/5) * np.cos(Y/5)

# Load the map image
from PIL import Image
img = Image.open('/home/pmarcone/projects/MapPlot/map_image.png')
img_array = np.array(img)

# Normalize image array to 0-1 range if needed
if img_array.dtype == np.uint8:
    img_array = img_array / 255.0

# Resize image to match mesh grid size
from PIL import Image as PILImage
img_resized = PILImage.fromarray((img_array * 255).astype(np.uint8)).resize((X.shape[1], X.shape[0]))
img_resized_array = np.array(img_resized) / 255.0

# Plot the cloth surface with the image texture
# Use image colors directly instead of colormap
facecolors = img_resized_array[:, :, :3]
ax.plot_surface(X, Y, Z, rstride=1, cstride=1, facecolors=facecolors)

ax.set_xlabel('X')
ax.set_ylabel('Y')
ax.set_zlabel('Z')
ax.set_title('3D Low Resolution Cloth')
ax.view_init(elev=25, azim=45)
ax.axis('off')

plt.show()

