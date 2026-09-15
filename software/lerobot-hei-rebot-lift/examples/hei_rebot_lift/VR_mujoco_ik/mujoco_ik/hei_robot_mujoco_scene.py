#!/usr/bin/env python
"""Build the HEI robot MuJoCo model with a lightweight debug environment."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import mujoco


SCENE_ASSET_DIR = Path(__file__).resolve().parent / "model" / "HEI_robot_urdf" / "scene_assets"
SAFETY_AREA_HALF_SIZE_M = 2.0
START_AREA_HALF_SIZE_M = 0.35
LINE_HALF_WIDTH_M = 0.015
LINE_HALF_HEIGHT_M = 0.003

# 桌面放在机器人正前方，尺寸兼顾双臂可达范围和底盘调试空间。
TABLE_CENTER_X_M = 0.92
TABLE_CENTER_Y_M = 0.0
TABLE_HALF_LENGTH_X_M = 0.48
TABLE_HALF_WIDTH_Y_M = 0.62
TABLE_TOP_Z_M = 0.78
TABLE_TOP_HALF_THICKNESS_M = 0.035


@dataclass(frozen=True)
class GraspableObjectSpec:
    """Stable-grasp metadata shared by the scene and VR simulator."""

    body_name: str
    geom_name: str
    initial_pos: tuple[float, float, float]
    initial_quat: tuple[float, float, float, float]
    support_height_m: float
    grasp_radius_m: float


GRASPABLE_OBJECTS = (
    GraspableObjectSpec(
        body_name="hei_object_cube_red",
        geom_name="hei_object_cube_red_geom",
        initial_pos=(0.70, -0.28, TABLE_TOP_Z_M + 0.04),
        initial_quat=(1.0, 0.0, 0.0, 0.0),
        support_height_m=0.04,
        grasp_radius_m=0.11,
    ),
    GraspableObjectSpec(
        body_name="hei_object_cube_green",
        geom_name="hei_object_cube_green_geom",
        initial_pos=(0.70, 0.0, TABLE_TOP_Z_M + 0.04),
        initial_quat=(1.0, 0.0, 0.0, 0.0),
        support_height_m=0.04,
        grasp_radius_m=0.11,
    ),
    GraspableObjectSpec(
        body_name="hei_object_cube_blue",
        geom_name="hei_object_cube_blue_geom",
        initial_pos=(0.70, 0.28, TABLE_TOP_Z_M + 0.04),
        initial_quat=(1.0, 0.0, 0.0, 0.0),
        support_height_m=0.04,
        grasp_radius_m=0.11,
    ),
    GraspableObjectSpec(
        body_name="hei_object_banana",
        geom_name="hei_object_banana_geom",
        initial_pos=(1.03, 0.0, TABLE_TOP_Z_M + 0.020),
        initial_quat=(0.9848, 0.0, 0.0, 0.1736),
        support_height_m=0.020,
        grasp_radius_m=0.14,
    ),
)

SCENE_GEOMS = (
    "hei_ground",
    "hei_safety_front",
    "hei_safety_rear",
    "hei_safety_left",
    "hei_safety_right",
    "hei_start_front",
    "hei_start_rear",
    "hei_start_left",
    "hei_start_right",
    "hei_world_axis_x",
    "hei_world_axis_y",
    "hei_world_axis_z",
    "hei_table_top",
    "hei_table_leg_front_left",
    "hei_table_leg_front_right",
    "hei_table_leg_rear_left",
    "hei_table_leg_rear_right",
    *(obj.geom_name for obj in GRASPABLE_OBJECTS),
)


def _add_line_box(
    spec: mujoco.MjSpec,
    name: str,
    pos: list[float],
    size: list[float],
    rgba: list[float],
) -> None:
    spec.worldbody.add_geom(
        name=name,
        type=mujoco.mjtGeom.mjGEOM_BOX,
        pos=pos,
        size=size,
        rgba=rgba,
        contype=0,
        conaffinity=0,
    )


def _add_floor_and_sky(spec: mujoco.MjSpec) -> None:
    # 程序纹理不依赖外部图片，复制项目后仍能得到一致的天空和方格地面。
    spec.add_texture(
        name="hei_sky",
        type=mujoco.mjtTexture.mjTEXTURE_SKYBOX,
        builtin=mujoco.mjtBuiltin.mjBUILTIN_GRADIENT,
        rgb1=[0.32, 0.43, 0.55],
        rgb2=[0.72, 0.78, 0.84],
        width=512,
        height=512,
    )
    spec.add_texture(
        name="hei_ground_grid",
        type=mujoco.mjtTexture.mjTEXTURE_2D,
        builtin=mujoco.mjtBuiltin.mjBUILTIN_CHECKER,
        mark=mujoco.mjtMark.mjMARK_EDGE,
        # 颜色以旧场景 floor="0.65 0.68 0.72" 为中心，只保留轻微方格明暗差。
        rgb1=[0.59, 0.62, 0.66],
        rgb2=[0.69, 0.72, 0.76],
        markrgb=[0.30, 0.32, 0.35],
        width=512,
        height=512,
    )
    ground_material = spec.add_material(
        name="hei_ground_material",
        texrepeat=[12.0, 12.0],
        texuniform=True,
        reflectance=0.05,
        specular=0.15,
        shininess=0.2,
    )
    ground_material.textures[mujoco.mjtTextureRole.mjTEXROLE_RGB] = "hei_ground_grid"
    spec.worldbody.add_geom(
        name="hei_ground",
        type=mujoco.mjtGeom.mjGEOM_PLANE,
        pos=[0.0, 0.0, -0.002],
        size=[0.0, 0.0, 0.05],
        material="hei_ground_material",
        contype=0,
        conaffinity=0,
    )


def _add_lights(spec: mujoco.MjSpec) -> None:
    # MuJoCo 默认相机灯仍会照亮模型，这里的主光降低到 0.52，避免金属表面过曝。
    spec.worldbody.add_light(
        name="hei_key_light",
        pos=[0.0, -0.6, 1.5],
        dir=[0.0, 0.0, -1.0],
        type=mujoco.mjtLightType.mjLIGHT_DIRECTIONAL,
        castshadow=True,
        diffuse=[0.52, 0.52, 0.52],
        ambient=[0.0, 0.0, 0.0],
        specular=[0.20, 0.20, 0.20],
    )
    # 前侧只做很弱的冷色补光，避免背光面全黑，但不会再次把模型照白。
    spec.worldbody.add_light(
        name="hei_fill_light",
        pos=[2.5, -2.5, 2.4],
        dir=[-0.6, 0.5, -0.65],
        type=mujoco.mjtLightType.mjLIGHT_DIRECTIONAL,
        castshadow=False,
        diffuse=[0.08, 0.09, 0.12],
        ambient=[0.0, 0.0, 0.0],
        specular=[0.02, 0.02, 0.03],
    )


def _add_floor_markings(spec: mujoco.MjSpec) -> None:
    safety_color = [0.95, 0.62, 0.08, 0.90]
    start_color = [0.05, 0.72, 0.70, 0.95]
    z = 0.004
    half = SAFETY_AREA_HALF_SIZE_M
    start = START_AREA_HALF_SIZE_M

    # 橙色 4 x 4 m 边框表示建议调试安全区域。
    for name, pos, size in (
        ("hei_safety_front", [half, 0.0, z], [LINE_HALF_WIDTH_M, half, LINE_HALF_HEIGHT_M]),
        ("hei_safety_rear", [-half, 0.0, z], [LINE_HALF_WIDTH_M, half, LINE_HALF_HEIGHT_M]),
        ("hei_safety_left", [0.0, half, z], [half, LINE_HALF_WIDTH_M, LINE_HALF_HEIGHT_M]),
        ("hei_safety_right", [0.0, -half, z], [half, LINE_HALF_WIDTH_M, LINE_HALF_HEIGHT_M]),
    ):
        _add_line_box(spec, name, pos, size, safety_color)

    # 青色 0.7 x 0.7 m 方框标记机器人启动位置和朝向参考原点。
    for name, pos, size in (
        ("hei_start_front", [start, 0.0, z + 0.001], [0.008, start, LINE_HALF_HEIGHT_M]),
        ("hei_start_rear", [-start, 0.0, z + 0.001], [0.008, start, LINE_HALF_HEIGHT_M]),
        ("hei_start_left", [0.0, start, z + 0.001], [start, 0.008, LINE_HALF_HEIGHT_M]),
        ("hei_start_right", [0.0, -start, z + 0.001], [start, 0.008, LINE_HALF_HEIGHT_M]),
    ):
        _add_line_box(spec, name, pos, size, start_color)


def _add_world_axes(spec: mujoco.MjSpec) -> None:
    # MuJoCo/机器人常用配色：X 红、Y 绿、Z 蓝，起点就是底盘初始中心。
    axes = (
        ("x", [0.0, 0.0, 0.025, 0.65, 0.0, 0.025], [0.90, 0.12, 0.10, 1.0]),
        ("y", [0.0, 0.0, 0.025, 0.0, 0.65, 0.025], [0.10, 0.72, 0.18, 1.0]),
        ("z", [0.0, 0.0, 0.025, 0.0, 0.0, 0.65], [0.12, 0.30, 0.95, 1.0]),
    )
    for axis, fromto, rgba in axes:
        spec.worldbody.add_geom(
            name=f"hei_world_axis_{axis}",
            type=mujoco.mjtGeom.mjGEOM_CYLINDER,
            fromto=fromto,
            size=[0.012],
            rgba=rgba,
            contype=0,
            conaffinity=0,
        )
        spec.worldbody.add_geom(
            name=f"hei_world_axis_{axis}_tip",
            type=mujoco.mjtGeom.mjGEOM_SPHERE,
            pos=fromto[3:],
            size=[0.028],
            rgba=rgba,
            contype=0,
            conaffinity=0,
        )


def _add_table(spec: mujoco.MjSpec) -> None:
    top_center_z = TABLE_TOP_Z_M - TABLE_TOP_HALF_THICKNESS_M
    table = spec.worldbody.add_body(
        name="hei_table",
        pos=[TABLE_CENTER_X_M, TABLE_CENTER_Y_M, 0.0],
    )
    table.add_geom(
        name="hei_table_top",
        type=mujoco.mjtGeom.mjGEOM_BOX,
        pos=[0.0, 0.0, top_center_z],
        size=[TABLE_HALF_LENGTH_X_M, TABLE_HALF_WIDTH_Y_M, TABLE_TOP_HALF_THICKNESS_M],
        rgba=[0.34, 0.25, 0.18, 1.0],
        contype=0,
        conaffinity=0,
    )

    leg_half_width = 0.035
    leg_half_height = top_center_z * 0.5
    leg_x = TABLE_HALF_LENGTH_X_M - 0.08
    leg_y = TABLE_HALF_WIDTH_Y_M - 0.08
    for name, x, y in (
        ("hei_table_leg_front_left", leg_x, leg_y),
        ("hei_table_leg_front_right", leg_x, -leg_y),
        ("hei_table_leg_rear_left", -leg_x, leg_y),
        ("hei_table_leg_rear_right", -leg_x, -leg_y),
    ):
        table.add_geom(
            name=name,
            type=mujoco.mjtGeom.mjGEOM_BOX,
            pos=[x, y, leg_half_height],
            size=[leg_half_width, leg_half_width, leg_half_height],
            rgba=[0.16, 0.17, 0.18, 1.0],
            contype=0,
            conaffinity=0,
        )


def _add_graspable_objects(spec: mujoco.MjSpec) -> None:
    cube_colors = (
        [0.82, 0.16, 0.12, 1.0],
        [0.16, 0.66, 0.25, 1.0],
        [0.12, 0.35, 0.86, 1.0],
    )
    for object_spec, color in zip(GRASPABLE_OBJECTS[:3], cube_colors, strict=True):
        body = spec.worldbody.add_body(
            name=object_spec.body_name,
            pos=list(object_spec.initial_pos),
            quat=list(object_spec.initial_quat),
        )
        body.add_geom(
            name=object_spec.geom_name,
            type=mujoco.mjtGeom.mjGEOM_BOX,
            size=[0.04, 0.04, 0.04],
            rgba=color,
            contype=0,
            conaffinity=0,
        )

    banana_dir = SCENE_ASSET_DIR / "ycb_011_banana"
    banana_obj = banana_dir / "textured.obj"
    banana_texture = banana_dir / "texture_map.png"
    missing = [path for path in (banana_obj, banana_texture) if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing local YCB banana asset(s): {missing}")

    # URDF 自带 compiler meshdir="../meshes"。使用 MjSpec 内存资源可避免新增
    # 场景资产被错误解析到机器人网格目录，也不会把本机绝对路径写入模型。
    banana_mesh_asset = "hei_ycb_011_banana.obj"
    banana_texture_asset = "hei_ycb_011_banana.png"
    obj_lines = banana_obj.read_bytes().splitlines()
    obj_without_mtl = b"\n".join(line for line in obj_lines if not line.startswith(b"mtllib "))
    spec.assets[f"../meshes/{banana_mesh_asset}"] = obj_without_mtl
    spec.assets[banana_texture_asset] = banana_texture.read_bytes()
    spec.add_mesh(
        name="hei_ycb_banana_mesh",
        file=banana_mesh_asset,
        smoothnormal=True,
    )
    spec.add_texture(
        name="hei_ycb_banana_texture",
        type=mujoco.mjtTexture.mjTEXTURE_2D,
        file=banana_texture_asset,
    )
    banana_material = spec.add_material(
        name="hei_ycb_banana_material",
        specular=0.08,
        shininess=0.10,
    )
    banana_material.textures[mujoco.mjtTextureRole.mjTEXROLE_RGB] = "hei_ycb_banana_texture"

    banana_spec = GRASPABLE_OBJECTS[3]
    banana_body = spec.worldbody.add_body(
        name=banana_spec.body_name,
        pos=list(banana_spec.initial_pos),
        quat=list(banana_spec.initial_quat),
    )
    banana_body.add_geom(
        name=banana_spec.geom_name,
        type=mujoco.mjtGeom.mjGEOM_MESH,
        meshname="hei_ycb_banana_mesh",
        material="hei_ycb_banana_material",
        contype=0,
        conaffinity=0,
    )


def build_mujoco_model(urdf_path: str | Path, *, add_environment: bool = True) -> mujoco.MjModel:
    """Compile the robot URDF, optionally adding the non-physical debug scene."""
    urdf_path = Path(urdf_path).expanduser().resolve()
    if not add_environment:
        return mujoco.MjModel.from_xml_path(str(urdf_path))

    spec = mujoco.MjSpec.from_file(str(urdf_path))
    _add_floor_and_sky(spec)
    _add_lights(spec)
    _add_floor_markings(spec)
    _add_world_axes(spec)
    _add_table(spec)
    _add_graspable_objects(spec)
    return spec.compile()
