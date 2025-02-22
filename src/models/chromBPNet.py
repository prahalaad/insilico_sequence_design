import numpy as np
import tensorflow as tf

from tensorflow.keras.models import load_model
from tensorflow.keras.utils import get_custom_objects

import chrombpnet.training.utils.losses as losses

import shap
import tensorflow as tf
# disable eager execution so shap deep explainer wont break
tf.compat.v1.disable_eager_execution()

import chrombpnet.evaluation.interpret.shap_utils as shap_utils
import chrombpnet.evaluation.interpret.input_utils as input_utils
from chrombpnet.evaluation.interpret.interpret import generate_shap_dict

def load_trained_model(model_path):
    
    '''
    Load pretrained ChromBPNet model.
    
    '''

    custom_objects={'tf': tf, 
                    'multinomial_nll': losses.multinomial_nll} 
    get_custom_objects().update(custom_objects)  
    
    model=load_model(model_path, compile=False)

    return model

def check_sequence(sequence_onehot):

    try:
        sequence_onehot = np.array(sequence_onehot)
        if sequence_onehot.ndim==2:
            sequence_onehot = np.expand_dims(sequence_onehot,0)
    except:
        raise ValueError('Input must be formatted as (n_batches, n_bases, 4)')

    try:
        assert sequence_onehot.ndim==3
        if sequence_onehot.shape[1]>2114:
            midpoint = int(sequence_onehot.shape[1]/2)
            sequence_onehot = sequence_onehot[:,midpoint-int(2114/2):midpoint+int(2114/2)]
        assert sequence_onehot.shape[1]==2114
        assert sequence_onehot.shape[2]==4
    except:
        raise ValueError('One hot DNA sequence is not properly formatted.')
    
    return sequence_onehot

def predict_accessibility(sequence_onehot, model, mode='profile'):

    '''
    Predict mean profile head output.

    '''
    sequence_onehot = check_sequence(sequence_onehot)

    if mode=='profile':
        prediction = model.predict_on_batch(sequence_onehot)[0]
        prediction = prediction.mean(axis=-1)
    elif mode=='count':
        prediction = model.predict_on_batch(sequence_onehot)[1]
        prediction=prediction.flatten()[0]

    return prediction

def compute_attribution(sequence_onehot, model, mode='scoring'):

    '''
    Compute DeepSHAP attribution.
    
    '''
    
    sequence_onehot = check_sequence(sequence_onehot)

    outlen = model.output_shape[0][1]

    profile_model_input = model.input
    profile_input = sequence_onehot
    counts_model_input = model.input
    counts_input = sequence_onehot

    weightedsum_meannormed_logits = shap_utils.get_weightedsum_meannormed_logits(model)
    profile_model_profile_explainer = shap.explainers.deep.TFDeepExplainer(
                                      (profile_model_input, weightedsum_meannormed_logits),
                                       shap_utils.shuffle_several_times,
                                       combine_mult_and_diffref=shap_utils.combine_mult_and_diffref)

    profile_shap_scores = profile_model_profile_explainer.shap_values(profile_input, progress_message=100)
    profile_scores_dict = generate_shap_dict(sequence_onehot, profile_shap_scores)

    if mode=='scoring': return profile_scores_dict['projected_shap']['seq'].sum(1).mean(-1)
    else: return profile_scores_dict['projected_shap']['seq']