import math
import typing
from abc import ABC, abstractmethod

import numpy as np
import tensorflow as tf
import tensorflow_addons as tfa

from kerasltiprovider.assignment import ValidationData


def rotate(image: tf.Tensor, max_rotation_degrees: float) -> tf.Tensor:
    max_rot_rad = math.radians(max_rotation_degrees)
    random_angles = tf.random.uniform(shape=(), minval=-max_rot_rad, maxval=max_rot_rad)
    return tfa.image.rotate(image, random_angles)


def zoom(x: tf.Tensor, scales: typing.List[float]) -> tf.Tensor:
    boxes = np.zeros((len(scales), 4))

    for i, scale in enumerate(scales):
        x1 = y1 = 0.5 - (0.5 * scale)
        x2 = y2 = 0.5 + (0.5 * scale)
        boxes[i] = [x1, y1, x2, y2]

    def random_crop(img: tf.Tensor) -> tf.Tensor:
        # Create different crops for an image
        crops = tf.image.crop_and_resize(
            [img], boxes=boxes, box_indices=np.zeros(len(scales)), crop_size=(32, 32)
        )
        # Return a random crop
        return crops[
            tf.random.uniform(shape=[], minval=0, maxval=len(scales), dtype=tf.int32)
        ]

    choice = tf.random.uniform(shape=[], minval=0.0, maxval=1.0, dtype=tf.float32)

    # Only apply cropping 50% of the time
    image = tf.cond(choice < 0.5, lambda: x, lambda: random_crop(x))
    return image


def color(x: tf.Tensor) -> tf.Tensor:
    x = tf.image.random_hue(x, 0.08)
    x = tf.image.random_saturation(x, 0.6, 1.6)
    x = tf.image.random_brightness(x, 0.05)
    x = tf.image.random_contrast(x, 0.7, 1.3)
    return x


def flip(x: tf.Tensor) -> tf.Tensor:
    x = tf.image.random_flip_left_right(x)
    x = tf.image.random_flip_up_down(x)
    return x


class PostprocessingStep(ABC):
    @abstractmethod
    def process(self, validation_data: ValidationData) -> ValidationData:
        pass


class Augment(PostprocessingStep):
    def __init__(
        self,
        flip: typing.Optional[bool] = None,
        color: typing.Optional[bool] = None,
        zoom: typing.Optional[typing.List[float]] = None,
        rotate: typing.Optional[float] = None,
    ):
        self.flip = flip
        self.color = color
        self.zoom = zoom
        self.rotate = rotate

    def augment(self, image: tf.Tensor) -> tf.Tensor:
        if self.flip is not None:
            image = flip(image)
        if self.color is not None:
            image = color(image)
        if self.rotate is not None:
            image = rotate(image, max_rotation_degrees=self.rotate)
        if self.zoom is not None:
            image = zoom(image, scales=self.zoom)
        return image

    def process(self, validation_data: ValidationData) -> ValidationData:
        validation_data.dataset = validation_data.dataset.map(
            lambda i, l: (self.augment(i), l)
        )
        return validation_data
