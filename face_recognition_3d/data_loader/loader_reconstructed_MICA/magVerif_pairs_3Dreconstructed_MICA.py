'''
    Bernardo: Synthetic Faces GPMM dataset.
'''

from __future__ import print_function

from math import ceil, floor
import os
import os.path
import json
import numpy as np
import sys
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = BASE_DIR
sys.path.append(os.path.join(ROOT_DIR, '../../../utils'))
import provider
import struct
from plyfile import PlyData

# from tree_lfw_3Dreconstructed_MICA import TreeLFW_3DReconstructedMICA
from data_loader.loader_reconstructed_MICA.tree_MagVerif_3Dreconstructed_MICA import TreeMAGFACE_3DReconstructedMICA

def pc_normalize(pc):
    # Bernardo
    pc /= 100
    pc = (pc - pc.min()) / (pc.max() - pc.min())

    # l = pc.shape[0]
    centroid = np.mean(pc, axis=0)
    pc = pc - centroid
    m = np.max(np.sqrt(np.sum(pc**2, axis=1)))
    pc = pc / m

    return pc

class MAGFACE_Evaluation_3D_Reconstructed_MICA_Dataset_Pairs:
    def __init__(self, root, protocol_file_path='pairs.txt', batch_size = 32, npoints = 2900, normalize=True, normal_channel=False, modelnet10=False, cache_size=15000, shuffle=False):
        self.root = root
        self.batch_size = batch_size
        self.npoints = npoints
        self.normalize = normalize
        self.normal_channel = normal_channel

        # Bernardo
        # file_ext = '.ply'
        file_ext = 'mesh_centralized-nosetip_with-normals_filter-radius=100.npy'

        # protocol_file_path = root + '/pairs.txt'
        all_pairs_paths_label, folds_indexes, pos_pair_label, neg_pair_label = TreeMAGFACE_3DReconstructedMICA().load_all_pairs_samples_from_protocol_file(root, protocol_file_path, file_ext)

        self.datapath = all_pairs_paths_label

        # self.cat = ['0', '1']    # Bernardo
        self.cat = [neg_pair_label, pos_pair_label]    # Bernardo
        self.classes = dict(zip(self.cat, range(len(self.cat))))  
        self.num_classes = len(self.cat)
        # print('self.cat:', self.cat)
        # print('self.classes:', self.classes)
        # print('self.num_classes:', self.num_classes)
        # sys.exit(0)

        self.cache_size = cache_size # how many data points to cache in memory
        self.cache = {} # from index to (point_set, cls) tuple

        self.shuffle = shuffle

        self.reset()


    def _augment_batch_data(self, batch_data):
        if self.normal_channel:
            rotated_data = provider.rotate_point_cloud_with_normal(batch_data)
            rotated_data = provider.rotate_perturbation_point_cloud_with_normal(rotated_data)
        else:
            rotated_data = provider.rotate_point_cloud(batch_data)
            rotated_data = provider.rotate_perturbation_point_cloud(rotated_data)
    
        jittered_data = provider.random_scale_point_cloud(rotated_data[:,:,0:3])
        jittered_data = provider.shift_point_cloud(jittered_data)
        jittered_data = provider.jitter_point_cloud(jittered_data)
        rotated_data[:,:,0:3] = jittered_data
        return provider.shuffle_points(rotated_data)


    def _readply(self, file):
        with open(file, 'rb') as f:
            plydata = PlyData.read(f)
            num_verts = plydata['vertex'].count
            vertices = np.zeros(shape=(num_verts, 3), dtype=np.float32)
            vertices[:,0] = plydata['vertex'].data['x']
            vertices[:,1] = plydata['vertex'].data['y']
            vertices[:,2] = plydata['vertex'].data['z']
            # vertices[:,3] = plydata['vertex'].data['red']
            # vertices[:,4] = plydata['vertex'].data['green']
            # vertices[:,5] = plydata['vertex'].data['blue']
            # print('plydata:', plydata)
            # print('vertices:', vertices)
            # sys.exit(0)
            return vertices


    def _get_item(self, index): 
        if index in self.cache:
            point_set1, point_set2, cls = self.cache[index]
        else:
            fn = self.datapath[index]
            cls = self.classes[self.datapath[index][0]]
            cls = np.array([cls]).astype(np.int32)

            # # Bernardo
            # print('lfw_3Dreconstructed_MICA_dataset.py: _get_item(): loading file:', fn[1])
            # print('lfw_3Dreconstructed_MICA_dataset.py: _get_item(): loading file:', fn[2])
            # print('label:', cls)
            # print('-------------------------')

            # point_set = np.loadtxt(fn[1],delimiter=',').astype(np.float32)   # original
            if fn[1].endswith('.npy'):
                point_set1 = np.load(fn[1]).astype(np.float32)                 # Bernardo
                point_set2 = np.load(fn[2]).astype(np.float32)                 # Bernardo
            elif fn[1].endswith('.ply'):
                point_set1 = self._readply(fn[1]).astype(np.float32)           # Bernardo
                point_set2 = self._readply(fn[2]).astype(np.float32)           # Bernardo

            # Bernardo
            if point_set1.shape[1] == 7:        # if contains curvature
                point_set1 = point_set1[:,:-1]  # remove curvature column
                point_set2 = point_set2[:,:-1]  # remove curvature column

            # Take the first npoints
            point_set1 = point_set1[0:self.npoints,:]
            point_set2 = point_set2[0:self.npoints,:]
            if self.normalize:
                point_set1[:,0:3] = pc_normalize(point_set1[:,0:3])
                point_set2[:,0:3] = pc_normalize(point_set2[:,0:3])
            if not self.normal_channel:
                point_set1 = point_set1[:,0:3]
                point_set2 = point_set2[:,0:3]
            if len(self.cache) < self.cache_size:
                self.cache[index] = (point_set1, point_set2, cls)
        return point_set1, point_set2, cls
        
    def __getitem__(self, index):
        return self._get_item(index)

    def __len__(self):
        return len(self.datapath)

    def num_channel(self):
        if self.normal_channel:
            return 6
        else:
            return 3

    def reset(self):
        self.idxs = np.arange(0, len(self.datapath))
        if self.shuffle:
            np.random.shuffle(self.idxs)
        self.num_batches = (len(self.datapath)+self.batch_size-1) // self.batch_size
        self.batch_idx = 0

    def has_next_batch(self):
        return self.batch_idx < self.num_batches

    def next_batch(self, augment=False):
        ''' returned dimension may be smaller than self.batch_size '''
        start_idx = self.batch_idx * self.batch_size
        end_idx = min((self.batch_idx+1) * self.batch_size, len(self.datapath))
        bsize = end_idx - start_idx
        # batch_data = np.zeros((bsize, self.npoints, self.num_channel()))
        batch_data = np.zeros((2, bsize, self.npoints, self.num_channel()))
        batch_label = np.zeros((bsize), dtype=np.int32)
        for i in range(bsize):
            # ps,cls = self._get_item(self.idxs[i+start_idx])       # original
            ps1, ps2, cls = self._get_item(self.idxs[i+start_idx])  # Bernardo

            # # TESTE
            # print('ps1:', ps1)
            # print('ps1.shape:', ps1.shape)
            # print('np.expand_dims(ps1, axis=1):', np.expand_dims(np.expand_dims(ps1, axis=0), axis=0).shape)
            # sys.exit(0)

            # batch_data[i] = ps      # original
            batch_data[0, i] = ps1    # Bernardo
            batch_data[1, i] = ps2    # Bernardo
            # batch_data[0, i] = np.expand_dims(ps1, axis=0)    # Bernardo
            # batch_data[1, i] = np.expand_dims(ps2, axis=0)    # Bernardo
            
            batch_label[i] = cls
        self.batch_idx += 1
        if augment: batch_data = self._augment_batch_data(batch_data)
        return batch_data, batch_label
    
if __name__ == '__main__':
    d = ModelNetDataset(root = '../data/modelnet40_normal_resampled', split='test')
    print(d.shuffle)
    print(len(d))
    import time
    tic = time.time()
    for i in range(10):
        ps, cls = d[i]
    print(time.time() - tic)
    print(ps.shape, type(ps), cls)

    print(d.has_next_batch())
    ps_batch, cls_batch = d.next_batch(True)
    print(ps_batch.shape)
    print(cls_batch.shape)
