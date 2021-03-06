"""MLflow integration for Keras."""

from __future__ import absolute_import

import os

import keras.backend as K
import pandas as pd

from mlflow import pyfunc
from mlflow.models import Model
import mlflow.tracking


def save_model(keras_model, path, conda_env=None, mlflow_model=Model()):
    """
    Save a Keras model to a path on the local file system.

    :param keras_model: Keras model to be saved.
    :param path: Local path where the model is to be saved.
    :param mlflow_model: MLflow model config this flavor is being added to.
    """
    import keras

    path = os.path.abspath(path)
    if os.path.exists(path):
        raise Exception("Path '{}' already exists".format(path))
    os.makedirs(path)
    model_file = os.path.join(path, "model.h5")
    keras_model.save(model_file)

    pyfunc.add_to_model(mlflow_model, loader_module="mlflow.keras",
                        data="model.h5", env=conda_env)
    mlflow_model.add_flavor("keras", keras_version=keras.__version__)
    mlflow_model.save(os.path.join(path, "MLmodel"))


def log_model(keras_model, artifact_path, **kwargs):
    """Log a Keras model as an MLflow artifact for the current run."""
    Model.log(artifact_path=artifact_path, flavor=mlflow.keras,
              keras_model=keras_model, **kwargs)


def _load_model(model_file):
    import keras.models
    return keras.models.load_model(os.path.abspath(model_file))


class _KerasModelWrapper:
    def __init__(self, keras_model, graph, sess):
        self.keras_model = keras_model
        self._graph = graph
        self._sess = sess

    def predict(self, dataframe):
        with self._graph.as_default():
            with self._sess.as_default():
                predicted = pd.DataFrame(self.keras_model.predict(dataframe))
        predicted.index = dataframe.index
        return predicted


def load_pyfunc(model_file):
    """
    Loads a Keras model as a PyFunc from the passed-in persisted Keras model file.

    :param model_file: Path to Keras model file.
    :return: PyFunc model.
    """
    if K._BACKEND == 'tensorflow':
        import tensorflow as tf
        graph = tf.Graph()
        sess = tf.Session(graph=graph)
        # By default tf backed models depend on the global graph and session.
        # We create an use new Graph and Session and store them with the model
        # This way the model is independent on the global state.
        with graph.as_default():
            with sess.as_default():  # pylint:disable=not-context-manager
                K.set_learning_phase(0)
                m = _load_model(model_file)
        return _KerasModelWrapper(m, graph, sess)
    else:
        raise Exception("Unsupported backend '%s'" % K._BACKEND)


def load_model(path, run_id=None):
    """
    Load a Keras model from a local file (if run_id is None) or a run.
    """
    if run_id is not None:
        path = mlflow.tracking.utils._get_model_log_dir(model_name=path, run_id=run_id)
    return _load_model(os.path.join(path, "model.h5"))
