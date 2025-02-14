"""CLI interface for this package"""

import json
import os
from typing import List, Optional

import albumentations as A
import click
from airo_dataset_tools.coco_tools.transform_dataset import apply_transform_to_coco_dataset
from airo_dataset_tools.cvat_labeling.convert_cvat_to_coco import cvat_image_to_coco
from airo_dataset_tools.data_parsers.coco import CocoKeypointsDataset
from airo_dataset_tools.fiftyone_viewer import view_coco_dataset


@click.group()
def cli() -> None:
    """CLI entrypoint for airo-dataset-tools"""


@cli.command(name="fiftyone-coco-viewer")  # no help, takes the docstring of the function.
@click.argument("annotations-json-path", type=click.Path(exists=True))
@click.option(
    "--dataset-dir",
    required=False,
    type=click.Path(exists=True),
    help="optional directory relative to which the image paths in the coco dataset are specified",
)
@click.option(
    "--label-types",
    "-l",
    multiple=True,
    type=click.Choice(["detections", "segmentations", "keypoints"]),
    help="add an argument for each label type you want to load (default: all)",
)
def view_coco_dataset_cli(
    annotations_json_path: str, dataset_dir: str, label_types: Optional[List[str]] = None
) -> None:
    """Explore COCO dataset with FiftyOne"""
    view_coco_dataset(annotations_json_path, dataset_dir, label_types)


@cli.command(name="convert-cvat-to-coco-keypoints")
@click.argument("cvat_xml_file", type=str, required=True)
@click.option("--add_bbox", is_flag=True, default=False, help="include bounding box in coco annotations")
@click.option("--add_segmentation", is_flag=True, default=False, help="include segmentation in coco annotations")
def convert_cvat_to_coco_cli(cvat_xml_file: str, add_bbox: bool, add_segmentation: bool) -> None:
    """Convert CVAT XML to COCO keypoints json"""
    coco = cvat_image_to_coco(cvat_xml_file, add_bbox=add_bbox, add_segmentation=add_segmentation)
    path = os.path.dirname(cvat_xml_file)
    filename = os.path.basename(cvat_xml_file)
    path = os.path.join(path, filename.split(".")[0] + ".json")
    with open(path, "w") as file:
        json.dump(coco, file)


@cli.command(name="resize-coco-keypoints-dataset")
@click.argument("annotations-json-path", type=click.Path(exists=True))
@click.option("--width", type=int, required=True)
@click.option("--height", type=int, required=True)
def resize_coco_keypoints_dataset(annotations_json_path: str, width: int, height: int) -> None:
    """Resize a COCO dataset. Will create a new directory with the resized dataset on the same level as the original dataset.
    Dataset is assumed to be
    /dir
        annotations.json # contains relative paths w.r.t. /dir
        ...
    """
    coco_dataset_dir = os.path.dirname(annotations_json_path)
    annotations_file_name = os.path.basename(annotations_json_path)
    dataset_parent_dir = os.path.dirname(coco_dataset_dir)
    transformed_dataset_dir = os.path.join(
        dataset_parent_dir, f"{annotations_file_name.split('.')[0]}_resized_{width}x{height}"
    )
    os.makedirs(transformed_dataset_dir, exist_ok=True)

    transforms = [A.Resize(height, width)]
    coco_json = json.load(open(annotations_json_path, "r"))
    coco_dataset = CocoKeypointsDataset(**coco_json)
    transformed_dataset = apply_transform_to_coco_dataset(
        transforms, coco_dataset, coco_dataset_dir, transformed_dataset_dir
    )

    transformed_dataset_dict = transformed_dataset.dict(exclude_none=True)
    with open(os.path.join(transformed_dataset_dir, annotations_file_name), "w") as f:
        json.dump(transformed_dataset_dict, f)
