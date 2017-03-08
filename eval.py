#!/user/bin/env python
""" Evaluate the correctness of the data files.
"""
from __future__ import absolute_import, division, print_function, with_statement


import codecs
import glob
import re


GT_ERROR_PATH = 'error.gt.txt'
GT_TXT_PATH   = 'gt'
OCR_TXT_PATH  = 'ocr'


OCR_UNICODE_REP = {
        chr(64256): 'ff',   # U+FB00
        chr(64257): 'fi',   # U+FB01
        chr(64258): 'fl',   # U+FB02
        chr(64259): 'ffi',  # U+FB03
        chr(64260): 'ffl',  # U+FB04
        }

# ASCII representations to 
GT_UNICODE_REP = {
        chr(198):   'AE',   # U+00C6
        chr(230):   'ae',   # U+00E6
        }


def gen_lines(path):
    """ Return lines of a concatinated text read from files in the given folder.
    """
    return (l
            for f in sorted(glob.glob(path + '/*.txt'))
            for l in codecs.open(f, 'r', 'utf-8').readlines())


def gen_lposs(path):
    """ Return lines and according line starting positions.
    """
    offset = 0
    lprev = ''
    for l in gen_lines(path):
        offset += len(lprev)
        lprev = l
        yield l, offset
    

def eval_text_match(gt_path=GT_TXT_PATH, ocr_path=OCR_TXT_PATH,
        err_path=GT_ERROR_PATH):
    """ Evaluate the contents of the ground truth and error-substituted OCR text
    are the same.
    """
    # Get a dictionary of the error information, where errors are indexed by
    # their positions.
    err_dict = {}
    for l in codecs.open(err_path, 'r', 'utf-8'):
        sp = l.split('\t')
        sp[0] = int(sp[0])
        if not re.search(r'ERROR', sp[-1]):
            if sp[0] in err_dict:
                err_dict[sp[0]] += [sp]
            else:
                err_dict[sp[0]] = [sp]

    # Check line match with error substituted.
    prev = None
    for gt_l, (ocr_l, offset) in zip(gen_lines(gt_path), gen_lposs(ocr_path)):
        errs = [e
                for pos in range(offset, offset + len(ocr_l))
                if pos in err_dict
                for e in err_dict[pos]]

        # Consider the cross-line error, for example, 'unfre-\nquent'. Since the
        # content of the next line is involved, we need to store the line info
        # and make decision after the next line is read. When merging two lines,
        # we need to remove the ending '-\n' to match with the error. In
        # addition, we need to insert two whitespace after the first word of the
        # current line to maintain the same offset for error substitutions
        # on the second merged line.
        def merge(l1, l2):
            try:
                pos = l2.index(' ')
            except ValueError:
                pos = len(l2)
            return l1[:-2] + l2[:pos] + '  ' + l2[pos:]
        if prev is not None:
            gt_l   = merge(prev[0], gt_l)
            ocr_l  = merge(prev[1], ocr_l)
            errs   = prev[2] + errs
            offset = prev[3]
        if len(errs) > 0 and len(errs[-1][1]) + errs[-1][0] >= offset + len(ocr_l):
            prev = (gt_l, ocr_l, errs, offset)
            continue
        else:
            prev = None

        # Substitute errors in the OCR text.
        ocr_sub = ocr_l
        sub_offset = 0
        for (e_pos, e_ocr, e_gt, e_gt_ascii, _) in errs:
            e_offset = e_pos - offset + sub_offset
            e_sub = e_gt_ascii if len(e_gt_ascii) > 0 else e_gt
            sub_offset += len(e_sub) - len(e_ocr)  # change due to substitutions
            ocr_sub = ocr_sub[:e_offset] + e_sub + ocr_sub[e_offset + len(e_ocr):]

        # Substitue unicode in GT and OCR text
        for k, v in  GT_UNICODE_REP.items(): gt_l = gt_l.replace(k, v)
        for k, v in OCR_UNICODE_REP.items(): ocr_sub = ocr_sub.replace(k, v)

        # Check alignment of non-whitespace characters.
        def next(gen):
            try:
                return gen.__next__()
            except StopIteration:
                return None
        gt_gen, ocr_gen = (c for c in gt_l), (c for c in ocr_sub)
        gt_c, ocr_c = ' ', ' '
        while gt_c is not None and ocr_c is not None:
            while gt_c  is ' ': gt_c  = next(gt_gen)
            while ocr_c is ' ': ocr_c = next(ocr_gen)
            if gt_c.lower() == ocr_c.lower():
                gt_c  = next(gt_gen)
                ocr_c = next(ocr_gen)
            else:
                raise Exception('character unmatch: {} ({}), {} ({}) \n'
                        '\t   in line ({}):\n\t\t GT: {}\n\t\tSUB: {}\n\t\tOCR: {}\n'
                        .format(gt_c, ord(gt_c), ocr_c, ord(ocr_c),
                                offset, gt_l[:-1], ocr_sub[:-1], ocr_l[:-1]))


def eval_err_list(err_path=GT_ERROR_PATH):
    """ Check the format of the ground error list file. """
    errors = [l.split('\t') for l in codecs.open(err_path, 'r', 'utf-8')]
    for pos, ocr, gt, gt_ascii, info in errors:

        # Check if there is any false error.
        if gt == ocr or (len(gt) and gt == gt_ascii):
            raise Exception('Format error: false error: {}'
                    .format((pos, ocr, gt, gt_ascii, info)))

        # Check if there is unicode GT name without ASCII version.
        if (not all(ord(c) < 128 for c in gt)
                and len(gt_ascii) == 0
                # some special types allow unicode
                and not (re.search(r'(person|place)-name', info)
                        or re.search(r'sound-simulation', info)
                        or re.search(r'special', info)
                        or re.search(r'punctuation', info))):
            raise Exception('Format error: gt_ascii do not exists: {}'
                    .format(pos))

        # Check if gt_ascii is in ASCII
        if not all(ord(c) < 128 for c in gt_ascii):
            raise Exception('Format error: gt_ascii is not in ASCII: {}'
                    .format(pos))

        # Check if there is any GT name can be further splitted.
        if re.match(r'\w+\W+$', gt) and int(pos) not in [258955, 457072]:
            raise Exception('Format error: gt contains multiple tokens: {}'
                    .format((pos, ocr, gt, gt_ascii, info)))
    


if __name__ == '__main__':
    print(chr(339))
    print(chr(230))
    print(chr(230))
    eval_text_match()
    eval_err_list()
    print('Done!')

