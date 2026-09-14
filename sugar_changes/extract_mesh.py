import argparse
from sugar_utils.general_utils import str2bool
from sugar_extractors.coarse_mesh import extract_mesh_from_coarse_sugar

if __name__ == "__main__":
    # Parser
    parser = argparse.ArgumentParser(description='Script to extract a mesh from a coarse SuGaR scene.')
    parser.add_argument('-s', '--scene_path',
                        type=str, 
                        help='path to the scene data to use.')
    parser.add_argument('-c', '--checkpoint_path', 
                        type=str, 
                        help='path to the vanilla 3D Gaussian Splatting Checkpoint to load.')
    parser.add_argument('-i', '--iteration_to_load', 
                        type=int, default=7000, 
                        help='iteration to load.')
    
    parser.add_argument('-m', '--coarse_model_path', type=str, default=None, help='')
    
    parser.add_argument('-l', '--surface_level', type=float, default=None, 
                        help='Surface level to extract the mesh at. If None, will extract levels 0.1, 0.3 and 0.5')
    parser.add_argument('-d', '--decimation_target', type=int, default=None, 
                        help='Target number of vertices to decimate the mesh to. If None, will decimate to 200_000 and 1_000_000.')
    parser.add_argument('--project_mesh_on_surface_points', type=str2bool, default=True, 
                        help='If True, project the mesh on the surface points for better details.')
    
    parser.add_argument('-o', '--mesh_output_dir',
                        type=str, default=None, 
                        help='path to the output directory.')
    
    parser.add_argument('-b', '--bboxmin', type=str, default=None, help='Min coordinates to use for foreground.')
    parser.add_argument('-B', '--bboxmax', type=str, default=None, help='Max coordinates to use for foreground.')
    parser.add_argument('--center_bbox', type=str2bool, default=True, help='If True, center the bounding box. Default is True.')
    
    parser.add_argument('--gpu', type=int, default=0, help='Index of GPU device to use.')
    
    parser.add_argument('--eval', type=str2bool, default=True, help='Use eval split.')
    parser.add_argument('--use_centers_to_extract_mesh', type=str2bool, default=False, 
                        help='If True, just use centers of the gaussians to extract mesh.')
    parser.add_argument('--use_marching_cubes', type=str2bool, default=False, 
                        help='If True, use marching cubes to extract mesh.')
    parser.add_argument('--use_vanilla_3dgs', type=str2bool, default=False,
                        help='If True, use vanilla 3DGS to extract mesh.')

    # ----- Multi-view depth-consistency point filtering (阶段2a 改动, 默认关闭) -----
    # 在 fg/bg 分离与 Poisson 之前，对表面采样点做多视角深度一致性投票剔点。
    # 关闭(mv_filter=False)时提取流程与基线逐位一致。详见 sugar_extractors/mv_consistency_filter.py。
    parser.add_argument('--mv_filter', type=str2bool, default=False,
                        help='If True, run multi-view depth-consistency point filtering before Poisson.')
    parser.add_argument('--mv_tau', type=float, default=0.02,
                        help='Relative depth tolerance for consistency vote (COLMAP default is 0.01).')
    parser.add_argument('--mv_min_consistent', type=int, default=2,
                        help='Keep a point only if consistent votes >= this (ACMM uses 2).')
    parser.add_argument('--mv_max_conflict', type=int, default=1,
                        help='Keep a point only if free-space conflict votes <= this.')
    parser.add_argument('--mv_n_ref_cams', type=int, default=30,
                        help='Number M of reference cameras whose depth maps are cached.')
    parser.add_argument('--mv_n_votes', type=int, default=0,
                        help='Per-point votes K: 0 or >=M means use all M reference cameras.')
    parser.add_argument('--mv_seed', type=int, default=0,
                        help='Seed for reference-camera sampling (and per-point K sampling).')

    args = parser.parse_args()
    
    # Call function
    extract_mesh_from_coarse_sugar(args)
    