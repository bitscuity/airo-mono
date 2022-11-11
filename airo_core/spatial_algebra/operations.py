"""
This file contains some operations on points and poses.

It also defines a helper class for a collection of points, but this is only used internally
to allow the user to directly interact with np.arrays to reduce friction.

i.e. the user can  call <transform>(points) where points is just a numpy array,
    instead of having to first convert the points to a specific format.
"""

import numpy as np

from airo_core.type_aliases import HomogeneousMatrixType, PointsType


class HomogeneousPoints:
    def __init__(self, points: PointsType):
        if not self.is_valid_points_type(points):
            raise ValueError(f"Invalid argument for {HomogeneousPoints.__name__}.__init__ ")
        if self.is_single_point(points):
            self._homogeneous_points = np.concatenate([points, np.ones(1, dtype=np.float32)])
            self._homogeneous_points = self._homogeneous_points[np.newaxis, :]
        else:
            self._homogeneous_points = np.concatenate(
                [points, np.ones((points.shape[0], 1), dtype=np.float32)], axis=1
            )

    @staticmethod
    def is_valid_points_type(points: PointsType) -> bool:
        if len(points.shape) == 1:
            if len(points) == 3:
                return True
        elif len(points.shape) == 2:
            if points.shape[1] == 3:
                return True
        return False

    @staticmethod
    def is_single_point(points: PointsType) -> bool:
        return len(points.shape) == 1

    @property
    def homogeneous_points(self):
        """Nx4 matrix representing the homogeneous points"""
        return self._homogeneous_points

    @property
    def points(self) -> PointsType:
        """Nx3 matrix representing the points"""
        # normalize points (for safety, should never be necessary with affine transforms)
        # but we've had bugs of this type with projection operations, so better safe than sorry?
        scalars = self._homogeneous_points[:, 3][:, np.newaxis]
        print(scalars)
        points = self.homogeneous_points[:, :3] / scalars
        # TODO: if the original poitns was (1,3) matrix, then the resulting points would be a (3,) vector.
        #  Is this desirable? and if not, how to avoid it?
        if points.shape[0] == 1:
            # single point -> create vector from 1x3 matrix
            return points[0]
        else:
            return points

    def apply_transform(self, homogeneous_transform_matrix: HomogeneousMatrixType):
        self._homogeneous_points = (homogeneous_transform_matrix @ self.homogeneous_points.transpose()).transpose()


def transform_points(homogeneous_transform_matrix: HomogeneousMatrixType, points: PointsType) -> PointsType:
    """Applies a transform to a (set of) point(s).

    Args:
        homogeneous_transform_matrix (HomogeneousMatrixType): _description_
        points (PointsType): _description_
    Returns:
        PointsType: (3,) vector or (N,3) matrix.
    """
    homogeneous_points = HomogeneousPoints(points)
    homogeneous_points.apply_transform(homogeneous_transform_matrix)
    return homogeneous_points.points
