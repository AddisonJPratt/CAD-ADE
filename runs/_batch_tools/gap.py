"""Out-of-band fit check on STLs reloaded from disk: place part B by a translation, report overlap and min gap."""
import sys, numpy as np, trimesh, manifold3d as m
def load(path, offset=(0,0,0), rot_z=None, about=(0,0,0), flip_x=False):
    mesh = trimesh.load_mesh(path)
    v = np.array(mesh.vertices, dtype=float); f = np.array(mesh.faces, dtype=np.uint32)
    if flip_x:   # 180 deg about X
        v[:,1] *= -1; v[:,2] *= -1
    if rot_z is not None:
        c, s = np.cos(np.radians(rot_z)), np.sin(np.radians(rot_z)); a = np.array(about)
        d = v - a; v = a + np.c_[c*d[:,0]-s*d[:,1], s*d[:,0]+c*d[:,1], d[:,2]]
    v = v + np.array(offset)
    return m.Manifold(m.Mesh(vert_properties=v.astype(np.float32), tri_verts=f))
def report(a, b, label="", search=5.0):
    print(f"{label}: overlap {(a ^ b).volume():.3f} mm3, min gap {a.min_gap(b, search):.3f} mm")
