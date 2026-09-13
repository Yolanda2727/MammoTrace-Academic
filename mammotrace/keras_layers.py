import keras

@keras.saving.register_keras_serializable(package="MammoTrace")
class ResNetPreprocess(keras.layers.Layer):
    def call(self,inputs):
        return keras.ops.flip(inputs,axis=-1)-keras.ops.convert_to_tensor([103.939,116.779,123.68],dtype=inputs.dtype)
    def get_config(self):return super().get_config()
