#!/usr/bin/python3

"""
Code to create and use an LSTM network to evaluate music
"""

import glob
import pickle
import random
import math
import re
import os
import numpy
import tensorflow as tf
from tensorflow.python.ops import rnn, rnn_cell
import music21 as m21

DATASET = "custom"  # options are custom and builtin

HM_EPOCHS = 5
N_CLASSES = 2
BATCH_SIZE = 64

CHUNK_SIZE = 128  # for one hot encoding pitch value; use 128 for MIDI values, 12 for pitch classes
N_CHUNKS = 64  # how many 16th notes should be examined at once?
RNN_SIZE = 256  # how many nodes to pass through

_x = tf.placeholder('float', [None, N_CHUNKS, CHUNK_SIZE])
_y = tf.placeholder(tf.float32, [None, 2])


def recurrent_neural_network(x):
    layer = {'weights': tf.Variable(tf.random_normal([RNN_SIZE, N_CLASSES])),
             'biases': tf.Variable(tf.random_normal([N_CLASSES]))}

    x = tf.transpose(x, [1, 0, 2])
    x = tf.reshape(x, [-1, CHUNK_SIZE])
    x = tf.split(x, N_CHUNKS, 0)

    lstm_cell = rnn_cell.BasicLSTMCell(RNN_SIZE)
    outputs, _ = rnn.static_rnn(lstm_cell, x, dtype=tf.float32)

    output = tf.matmul(outputs[-1], layer['weights']) + layer['biases']

    return output


def encode_pitch(midi_value):
    """ One hot encode MIDI values

        midi_value should be an integer between 0 and 127 (inclusive)
    """

    out = [0 for _ in range(CHUNK_SIZE)]
    out[midi_value] = 1

    return out


def reshape_music_data(input_data):
    """ reshape the music data to fit the network

        returns a len(input_data) x N_CHUNKS x CHUNK_SIZE numpy array
    """
    return numpy.array([[encode_pitch(note_val) for note_val in music] for music in input_data])


def train_neural_network(x, train_input, train_labels):
    prediction = recurrent_neural_network(x)
    cost = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(logits=prediction, labels=_y))
    optimizer = tf.train.AdamOptimizer().minimize(cost)

    training_data_ratio = 0.7
    split_point = int(len(train_labels) * training_data_ratio)

    model_accuracy = 0.0

    sess = tf.Session()

    while model_accuracy < 0.8:  # we want better than 80% accuracy
        sess.run(tf.global_variables_initializer())

        for epoch in range(HM_EPOCHS):
            epoch_loss = 0

            for _ in range(1):  # can be changed if multiple batches are used
                epoch_x = train_input[:split_point]
                epoch_y = train_labels[:split_point]
                epoch_x = reshape_music_data(epoch_x)

                _, c = sess.run([optimizer, cost], feed_dict={_x: epoch_x, _y: epoch_y})
                epoch_loss += c

            print('Epoch', epoch, 'completed out of', HM_EPOCHS, 'loss:', epoch_loss)

        correct = tf.equal(tf.argmax(prediction, 1), tf.argmax(_y, 1))

        accuracy = tf.reduce_mean(tf.cast(correct, 'float'))
        model_accuracy = accuracy.eval({_x: reshape_music_data(train_input[split_point:]), _y: train_labels[split_point:]}, session=sess)
        print('Accuracy:', model_accuracy)

    return sess, prediction


def evaluate_part(model, session, input_data):
    """ Use the provided `model` to determine how close `input_data` is to the training music. Use for a single imput """

    evaluation = session.run(model, feed_dict={_x: reshape_music_data([input_data])})[0]
    return (math.atan((evaluation[0] - evaluation[1]) / 5) + (math.pi / 2)) / math.pi


def convert_part_to_sixteenth_notes(part):
    """ convert part to all sixteenth notes """
    converted_part = []
    for note in part:
        if note.quarterLength / 0.25 - int(note.quarterLength / 0.25) != 0:
            continue
            # return False  # TODO be able to handle triplets

        note_len = note.quarterLength
        note.quarterLength = 0.25

        if isinstance(note, m21.chord.Chord):  # use only the top note from a Chord
            converted_part += [note[0].pitch.midi for _ in range(int(note_len / 0.25))]
        else:
            converted_part += [note.pitch.midi for _ in range(int(note_len / 0.25))]

    return converted_part


def normalize_score(score):
    """ Convert a score to C Major/a minor """
    orig_key = score.analyze('key')

    new_tonic = 'C'  # we assume the key is only Major or minor
    if orig_key.mode == 'minor':
        new_tonic = 'a'

    i = m21.interval.Interval(orig_key.tonic, m21.pitch.Pitch(new_tonic))

    return score.transpose(i)


def train_model_with_data():
    """ Train the LSTM network with data from the local corpus """
    training_file_names = glob.glob("../corpus/*.mid")
    training_data = []
    training_labels = []

    normalized_scores = []

    if not os.path.isdir("../scoreCache"):
        os.mkdir("../scoreCache")

    if DATASET == "custom":
        for score_title in training_file_names:
            pattern = re.compile(r"^.*[/\\]([^/\\]+\.mid)$")
            savable_file_name = pattern.search(score_title).group(1)

            if os.path.isfile("../scoreCache/" + savable_file_name + ".pickle"):
                normalized_scores.append(pickle.load(open("../scoreCache/" + savable_file_name + ".pickle", "rb")))
            else:
                my_score = m21.converter.parse(score_title)
                normalized_scores.append(normalize_score(my_score))
                pickle.dump(normalized_scores[-1], open("../scoreCache/" + savable_file_name + ".pickle", "wb"))
    else:
        music = m21.corpus.search(sourcePath='bach', numberOfParts=4)
        for piece in music:
            if os.path.isfile("../scoreCache/" + piece.corpusPath + ".pickle"):
                normalized_scores.append(pickle.load(open("../scoreCache/" + piece.corpusPath + ".pickle", "rb")))
            else:
                normalized_scores.append(normalize_score(piece.parse()))
                pickle.dump(normalized_scores[-1], open("../scoreCache/" + piece.corpusPath + ".pickle", "wb"))

    for score in normalized_scores:
        part = score.parts[0].flat.getElementsByClass(m21.note.Note)

        # convert the part entirely to sixteenth notes
        converted_part = convert_part_to_sixteenth_notes(part)
        if converted_part is False or not converted_part:
            continue  # part had triplets in it, skip

        measures_in_piece = len(converted_part) // 16

        for offset in range(measures_in_piece - 3):
            # sample = converted_part[offset * 16:(offset * 16) + N_CHUNKS]
            sample = []

            for i in range(N_CHUNKS):
                sample.append(converted_part[(offset * 16) + i])  # TODO simplify this?

            training_data.append(sample)
            training_labels.append([1, 0])

    # Generate an amount of junk data equal to the amount of good data
    for _ in range(len(training_data)):
        training_data.append([random.randrange(CHUNK_SIZE) for _ in range(N_CHUNKS)])
        training_labels.append([0, 1])

    # mix the good and bad data
    zipped_data = list(zip(training_data, training_labels))
    random.shuffle(zipped_data)
    training_data, training_labels = zip(*zipped_data)

    return train_neural_network(_x, training_data, training_labels)


def main():
    session, trained_model = train_model_with_data()

    # Test some music by different composers
    pieces_to_test = [
        '../corpus/suite_for_unaccompanied_cello_bwv-1007_1_(c)grossman.mid',
        '../corpus/Tune-87234.mid',
        '../nonBach/haydn_sonata_for_violin_1_(c)harfesoft.mid',
    ]

    for piece in pieces_to_test:
        score = normalize_score(m21.converter.parse(piece))

        print(piece, evaluate_part(trained_model, session, convert_part_to_sixteenth_notes(score.parts[0].flat.notes)[:64]))

    score = normalize_score(m21.converter.parse('../nonBach/scarlatti-d_esserciso_3_(c)icking-archive.mid'))
    print('../nonBach/scarlatti-d_esserciso_3_(c)icking-archive.mid', evaluate_part(trained_model, session, convert_part_to_sixteenth_notes(score.parts[0].flat.notes)[:64]))

    # Save the model for later use
    saver = tf.train.Saver()
    saver.save(session, './lstm_model')


if __name__ == "__main__":
    main()
