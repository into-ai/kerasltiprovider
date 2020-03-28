import typing

import numpy as np
import tensorflow as tf

VDC = typing.TypeVar("VDC", bound="ValidationData")


class ValidationData:
    def __init__(
        self,
        ds: tf.data.Dataset,
        resize: typing.Optional[typing.Tuple[int, ...]] = None,
    ) -> None:
        self.dataset = ds
        self.size = resize
        if resize is not None:
            self.dataset = self.dataset.map(
                lambda i, l: (tf.image.resize(i, resize), l)
            )

    @classmethod
    def from_numpy(
        cls: typing.Type[VDC], matrices: np.ndarray, labels: np.ndarray,
    ) -> VDC:
        assert matrices.shape[0] == labels.shape[0]
        dataset = tf.data.Dataset.from_tensor_slices((matrices, labels))
        return cls(dataset)

    @classmethod
    def from_model(cls: typing.Type[VDC], model_file: str, matrices: np.ndarray) -> VDC:
        model = tf.keras.models._load_model(model_file)
        predictions = model.predict(matrices)
        predicted_classes = np.array([np.argmax(p) for p in predictions])
        return cls(matrices, predicted_classes)

    def items(self) -> tf.data.Dataset:
        return self.dataset
