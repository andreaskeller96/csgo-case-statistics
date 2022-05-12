from binascii import unhexlify
import base64
import random

def long_to_bytes (val, endianness='big'):
    """
    Use :ref:`string formatting` and :func:`~binascii.unhexlify` to
    convert ``val``, a :func:`long`, to a byte :func:`str`.

    :param long val: The value to pack

    :param str endianness: The endianness of the result. ``'big'`` for
      big-endian, ``'little'`` for little-endian.

    If you want byte- and word-ordering to differ, you're on your own.

    Using :ref:`string formatting` lets us use Python's C innards.
    """

    # one (1) hex digit per four (4) bits
    width = val.bit_length()

    # unhexlify wants an even multiple of eight (8) bits, but we don't
    # want more digits than we need (hence the ternary-ish 'or')
    width += 8 - ((width % 8) or 8)

    # format width specifier: four (4) bits per hex digit
    fmt = '%%0%dx' % (width // 4)

    # prepend zero (0) to the width, to zero-pad the output
    s = unhexlify(fmt % val)

    if endianness == 'little':
        # see http://stackoverflow.com/a/931095/309233
        s = s[::-1]

    return s

def utf16_decimals(char, chunk_size=2):
    # encode the character as big-endian utf-16
    encoded_char = char.encode('utf-16-be')

    # convert every `chunk_size` bytes to an integer
    decimals = []
    for i in range(0, len(encoded_char), chunk_size):
        chunk = encoded_char[i:i+chunk_size]
        decimals.append(int.from_bytes(chunk, 'big'))

    return decimals

def pkcs1pad2(data, keysize):
    if(keysize < len(data) + 11):
        return None
    buffer = [None] * keysize
    i = len(data) - 1
    while (i >= 0 and keysize>0):
        keysize -= 1
        buffer[keysize] = utf16_decimals(data[i])[0]
        i -= 1
    keysize -= 1
    buffer[keysize] = 0
    while (keysize>2):
        keysize -= 1
        buffer[keysize] = random.randrange(1,254)
    keysize -= 1
    buffer[keysize] = 2
    keysize -= 1
    buffer[keysize] = 0
    return int.from_bytes(buffer,byteorder='big', signed=False)

def encrypt_data(data, pubkey):
    if not pubkey:
        return False
    data = pkcs1pad2(data,(pubkey.n.bit_length()+7)>>3);
    if not data:
        return False
    data = pow(data, pubkey.e,pubkey.n)
    data = hex(data)
    #print(data)
    data = data[2:]
    #print(data)
    if len(data)%2!=0:
        data = "0"+data
    data = int(data, 16)
    data = long_to_bytes(data)
    data = base64.b64encode(data)
    return data.decode('ascii')