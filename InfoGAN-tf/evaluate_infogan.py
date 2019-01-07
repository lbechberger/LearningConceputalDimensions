#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This script contains only the code from run_infogan.py, necessary for the 
evaluation process.

Created on Mon Oct 29 

@author: christina
"""

import pickle
import numpy as np
import os, sys
import ast
import fcntl
import functools
import tensorflow as tf
from datetime import datetime
from configparser import RawConfigParser
from helperfunctions import infogan_discriminator, infogan_generator, to_grayscale
from scipy.misc import imread
from scipy import sum, average

timestamp = str(datetime.now()).replace(' ','-')
os.environ['KMP_DUPLICATE_LIB_OK']='True'
tfgan = tf.contrib.gan
ds = tf.contrib.distributions

# default values for options
options = {}
options['train_log_dir'] = 'logs'
options['output_dir'] = 'output'
options['training_file'] = '../data/uniform.pickle'
options['noise_dims'] = 62
options['latent_dims'] = 2
options['batch_size'] = 128
options['gen_lr'] = 1e-3
options['dis_lr'] = 2e-4
options['lambda'] = 1.0
options['epochs'] = '50'
options['type_latent'] = 'u'
options['g_weight_decay_gen'] = 2.5e-5
options['d_weight_decay_dis'] = 2.5e-5

# read configuration file
model_name = sys.argv[1] #takes name of the modeltitle as an argument, e.g. '2018-12-05-12:12:49.8405241dummy.model'
config_name = sys.argv[2] #takes configuration name as an argument, e.g. 'dummy'
config = RawConfigParser(options)
config.read("grid_search.cfg")

def parse_range(key):
    value = options[key]
    parsed_value = ast.literal_eval(value)
    if isinstance(parsed_value, list):
        options[key] = parsed_value
    else:
        options[key] = [parsed_value]

# overwrite default values for options
if config.has_section(config_name):
    options['train_log_dir'] = config.get(config_name, 'train_log_dir')
    options['output_dir'] = config.get(config_name, 'output_dir')
    options['training_file'] = config.get(config_name, 'training_file')
    options['noise_dims'] = config.getint(config_name, 'noise_dims')
    options['latent_dims'] = config.getint(config_name, 'latent_dims')
    options['batch_size'] = config.getint(config_name, 'batch_size')
    options['gen_lr'] = config.getfloat(config_name, 'gen_lr')
    options['dis_lr'] = config.getfloat(config_name, 'dis_lr')
    options['lambda'] = config.getfloat(config_name, 'lambda')
    options['epochs'] = config.get(config_name, 'epochs')
    options['type_latent'] = config.get(config_name, 'type_latent')
    options['g_weight_decay_gen'] = config.get(config_name, 'g_weight_decay_gen')
    options['d_weight_decay_dis'] = config.get(config_name, 'd_weight_decay_dis')


parse_range('epochs')

# Set up the input
input_data = pickle.load(open(options['training_file'], 'rb'), encoding='latin1')
rectangles = np.array(list(map(lambda x: x[0], input_data['data'])), dtype=np.float32)
labels = np.array(list(map(lambda x: x[1:], input_data['data'])), dtype=np.float32)
dimension_names = input_data['dimensions']
length_of_data_set = len(rectangles)
images = rectangles.reshape((-1, 28, 28, 1))
dataset = tf.data.Dataset.from_tensor_slices((images, labels))
dataset = dataset.shuffle(20480).repeat().batch(options['batch_size'])
batch_images = dataset.make_one_shot_iterator().get_next()[0]

### 
def get_training_noise(batch_size, structured_continuous_dim, noise_dims):
    """Get unstructured and structured noise for InfoGAN.
    Args:
        batch_size: The number of noise vectors to generate.
        structured_continuous_dim: The number of dimensions of the uniform continuous noise.
        total_continuous_noise_dims: The number of continuous noise dimensions. This number includes the structured and unstructured noise.
    Returns:
        A 2-tuple of structured and unstructured noise. First element is the
        unstructured noise, and the second is the continuous structured noise."""
    # Get unstructurd noise.
    unstructured_noise = tf.random_normal([batch_size, noise_dims])

    # Get continuous noise Tensor.
    if options['type_latent'] == 'u':
        continuous_dist = ds.Uniform(-tf.ones([structured_continuous_dim]), tf.ones([structured_continuous_dim]))
        continuous_noise = continuous_dist.sample([batch_size])
    elif options['type_latent'] == 'n':
        continuous_noise = tf.random_normal([batch_size, structured_continuous_dim], mean = 0.0, stddev = 0.5)
    else:
        raise Exception("Unknown type of latent distribution: {0}".format(options['type_latent']))

    return [unstructured_noise], [continuous_noise]

# # Build the generator and discriminator.
# discriminator_fn = functools.partial(infogan_discriminator, continuous_dim=options['latent_dims'], d_weight_decay_dis=options['d_weight_decay_dis'])
# generator_fn = functools.partial(infogan_generator, g_weight_decay_gen=options['g_weight_decay_gen'])
# unstructured_inputs, structured_inputs = get_training_noise(options['batch_size'], options['latent_dims'], options['noise_dims'])
# 
# # Create the overall GAN
# gan_model = tfgan.infogan_model(
#     generator_fn=generator_fn,
#     discriminator_fn=discriminator_fn,
#     real_data=batch_images,
#     unstructured_generator_inputs=unstructured_inputs,
#     structured_generator_inputs=structured_inputs)



def get_training_noise(batch_size, structured_continuous_dim, noise_dims):
    """Get unstructured and structured noise for InfoGAN.
    Args:
        batch_size: The number of noise vectors to generate.
        structured_continuous_dim: The number of dimensions of the uniform continuous noise.
        total_continuous_noise_dims: The number of continuous noise dimensions. This number includes the structured and unstructured noise.
    Returns:
        A 2-tuple of structured and unstructured noise. First element is the
        unstructured noise, and the second is the continuous structured noise."""
    # Get unstructurd noise.
    unstructured_noise = tf.random_normal([batch_size, noise_dims])

    # Get continuous noise Tensor.
    if options['type_latent'] == 'u':
        continuous_dist = ds.Uniform(-tf.ones([structured_continuous_dim]), tf.ones([structured_continuous_dim]))
        continuous_noise = continuous_dist.sample([batch_size])
    elif options['type_latent'] == 'n':
        continuous_noise = tf.random_normal([batch_size, structured_continuous_dim], mean = 0.0, stddev = 0.5)
    else:
        raise Exception("Unknown type of latent distribution: {0}".format(options['type_latent']))

    return [unstructured_noise], [continuous_noise]

# calculate the number of training steps
num_steps = {}
max_num_steps = 0
for epoch in options['epochs']:
    steps = int( (epoch * length_of_data_set) / options['batch_size'] )
    num_steps[steps] = epoch
    max_num_steps = max(max_num_steps, steps)


#retrieve graph            
with tf.Session() as sess:
    sess.run(tf.global_variables_initializer())
    saver = tf.train.import_meta_graph('graphs/'+ model_name + '.meta')
    gan_model = saver.restore(sess, 'graphs/'+ model_name)
    print("Model restored")
    #gan_model = tf.saved_model.loader.load(sess, None, export_dir= gan_model_name)
    print(gan_model)
    print(tf.trainable_variables())
    
    #print(sess.run(tf.trainable_variables()[10]).eval())

    ###start evaluation###

    # now evaluate the current latent codes
    num_eval_steps = int( (1.0 * length_of_data_set) / options['batch_size'] )
    epoch_name = "{0}-ep{1}".format(config_name, epoch)
    print(epoch_name)

    # define the subsequent evaluation: ... first the data
    data_iterator = dataset.make_one_shot_iterator().get_next()
    real_images = data_iterator[0]
    real_targets = data_iterator[1]

    # ... and now the latent code
    ivate with tf.variable_scope(gan_model.discriminator_scope, reuse=True):
        latent_code = (discriminator_fn(real_images, None)[1][0]).loc # .loc = mean ?
        # discriminator_fn: A python lambda that takes `real_data`/`generated data`
        #       and `generator_inputs`. Outputs a 2-tuple of (logits, distribution_list).
        #       `logits` are in the range [-inf, inf]

    evaluation_output = tf.concat([latent_code, real_targets], axis=1)

    # compute all the outputs (= [latent_code, real_targets])
    table = []
    for i in range(num_eval_steps):
        rows = sess.run(evaluation_output)
        table.append(rows)
    table = np.concatenate(table, axis=0)

    # compute the ranges for each of the columns
    ranges = np.subtract(np.max(table, axis = 0), np.min(table, axis = 0))[:2]
    min_range = min(ranges)

    # compute correlations
    correlations = np.corrcoef(table, rowvar=False)

    output = {'n_latent' : options["latent_dims"], 'dimensions' : dimension_names, 'ranges' : ranges, 'table' : table}

    # store the so-far best matching interpretable dimension
    max_correlation_latent = [0.0]*options["latent_dims"]
    best_name_latent_correlation = [None]*options["latent_dims"]

    # iterate over all original dimensions
    for dim_idx, dimension in enumerate(dimension_names):

        # take Pearson's correlation coefficient for this dimension
        local_correlations = correlations[options["latent_dims"] + dim_idx][:options["latent_dims"]]

        output[dimension] = local_correlations

        # check whether we found a better interpretation for a latent variable...
        for latent_dim in range(options["latent_dims"]):
            if np.abs(local_correlations[latent_dim]) > max_correlation_latent[latent_dim]:
                max_correlation_latent[latent_dim] = np.abs(local_correlations[latent_dim])
                best_name_latent_correlation[latent_dim] = dimension

    # lower bound for best correlations
    interpretability_correlation = min(max_correlation_latent)
    # are no two latent variables best interpreted in the same way?
    all_different = (len(set(best_name_latent_correlation)) == options["latent_dims"])

    # dump all of this into a pickle file for later use
    with open(os.path.join(options['output_dir'], "{0}-ep{1}-{2}.pickle".format(config_name, epoch, timestamp)), 'wb') as f:
        pickle.dump(output, f)

    # some console output for debug purposes:
    print("\nOverall correlation-based interpretability: {0}".format(interpretability_correlation))
    print("Overall minimal range: {0}".format(min_range))
    print("Ended up with all different dimensions: {0}".format(all_different))
    for latent_dim in range(options["latent_dims"]):
        print("latent_{0} (range {1}): best interpreted as '{2}' ({3})".format(latent_dim, ranges[latent_dim], best_name_latent_correlation[latent_dim], max_correlation_latent[latent_dim]))
        for dimension in dimension_names:
            print("\t {0}: {1}".format(dimension, output[dimension][latent_dim]))

    # create output file if necessary
    file_name = os.path.join(options['output_dir'],'interpretabilities.csv')
    if not os.path.exists(file_name):
        with open(file_name, 'w') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write("config,data_set,overall_cor,min_range,different")
            for latent_dim in range(options["latent_dims"]):
                f.write(",range-{0}".format(latent_dim))
                f.write(",max-cor-{0},name-cor-{0}".format(latent_dim))
                for dimension in dimension_names:
                    f.write(",corr-{0}-{1}".format(dimension, latent_dim))
            f.write("\n")
            fcntl.flock(f, fcntl.LOCK_UN)

    # append information to output file
    with open(file_name, 'a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write("{0},{1},{2},{3},{4}".format(epoch_name, "rectangles", interpretability_correlation, min_range, all_different))
        for latent_dim in range(options["latent_dims"]):
            f.write(",{0}".format(ranges[latent_dim]))
            f.write(",{0},{1}".format(max_correlation_latent[latent_dim], best_name_latent_correlation[latent_dim]))
            for dimension in dimension_names:
                f.write(",{0}".format(output[dimension][latent_dim]))

        f.write("\n")
        fcntl.flock(f, fcntl.LOCK_UN)



# if model_name == 'evaluate' && config_name == 'all':
#     f = open("checkpoints.txt", "r")
#     model = []
#     for line in f:
#         model.append(line)
#         f.close()
#         print (model)
#         for checkpointfile in model:
#             checkpointfile.split(" ")
#             config_name = checkpointfile[0]
#             model_name = checkpointfile[1]
#             print("Evaluation for: " + model_name + " " + config_name)
#             full_evaluation(model_name, config_name)
