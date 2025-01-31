# -*- coding: utf-8 -*-

import torch
import re
import sys

bos_token = '<bos>'
pad_token = '<pad>'
eos_token = '<eos>'
unk_token = '<unk>'
start_token = '<SOT>'
end_token = '<EOT>'
space_token = '-#-'

fillerFOR = 'فلارفور'
fillerEMO = 'فلاريمو'
fillerPUN = 'فلاربون'
fillerSYM = 'فلارصيم'
fillerNUM = 'فلارنوم'
fillers = [fillerFOR, fillerEMO, fillerPUN, fillerSYM, fillerNUM]

LfillerFOR = '_FOREIGN_'
LfillerEMO = '_EMOTAG_'
LfillerPUN = '_PUNC_'
LfillerSYM = '_SYM_'
latin_fillers = [LfillerFOR, LfillerEMO, LfillerPUN, LfillerSYM]

NUM_list = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
SYM_list = ['½', '%', '°', '/', '\\', '"', '*', '&', '$', '#', '+', '@', '^']
PUNC_list = ['_', '-', '(', ')', '[', ']', '{', '}', '<', '>', ',', '.', ';', ':', '!', '?', '«', '»']

Arabic_sym = ['\\', '/', '@', '#', '$', '%', '^', '&', '*']
Arabic_punc =  ['.', ',', ':', '"', '،', 'ـ', '؟', '~', '!', ')', '(', '_', '+', '>', '<']
Arabic_char = ['ذ', 'ض', 'ص', 'ث', 'ق', 'ف', 'ف', 'غ', 'ع', 'ه', 'خ', 'ح', 'ج', 'د', 'ش', 'س', 'ي', 'ب', 'ل', 'ا', 'أ', 'ت', 'ن', 'م', 'ك', 'ط', 'ئ', 'ء', 'ؤ', 'ر', 'لا', 'ى','ة', 'ة', 'و', 'ز', 'ظ']

def is_arabic_word(string): 
    for c in string:
        if not c in Arabic_char:
            return False
    return True

def detect_fillers(string, fillers):

    filler_start = 0
    filler_end = -1

    filler_idx = 0
    f_idx = 0
    str_idx = 0
    search_status = 0
    search_start = 0

    res = []
    while str_idx < len(string):
        if string[str_idx] == fillers[filler_idx][f_idx]:
            search_status = 1
            f_idx += 1
            str_idx += 1 
        else:
            f_idx = 0
            filler_idx += 1
            if filler_idx >= len(fillers):
                filler_idx = 0
                str_idx += 1
                search_start = str_idx
            else:
                str_idx = search_start
            search_status = 0 

        if f_idx >= len(fillers[filler_idx]) and search_status == 1:
            res.append( (search_start,str_idx) )
            filler_idx = 0 
            search_start = str_idx
            search_status = 0
            f_idx = 0

    return res

def match_subseq(string, sym_list, search_start=0):
    start = search_start
    end = -1
    for s_idx in range(start, len(string)):
        if string[s_idx] in sym_list:
            if end == -1:
                start = s_idx
            end = s_idx+1
        elif end != -1:
            break
        
    return start, end

def replace_all(string, sym_list, replacement):

    start, end = match_subseq(string, sym_list)
    while end != -1:
        string = string[0:start] + replacement + string[end:]
        begin_search = start+len(replacement)
        start, end = match_subseq(string, sym_list, search_start=begin_search) 
    return string

def replace_all_num(string):
    return replace_all(string, NUM_list, fillerNUM)

def replace_all_pun(string):
    return replace_all(string, PUNC_list + Arabic_punc, fillerPUN)

def replace_all_sym(string):
    return replace_all(string, SYM_list + Arabic_sym, fillerSYM)

def replace_all_Lpun(string):
    return replace_all(string, PUNC_list + Arabic_punc, LfillerPUN)

def replace_all_Lsym(string):
    return replace_all(string, SYM_list + Arabic_sym, LfillerSYM)

num_pattern = re.compile('[0-9]+')
pun_pattern = re.compile('[_\-\(\)\[\]\{\}\<\>,\.;:\!\?\؟]+')
sym_pattern = re.compile('[½\%\-°/\\\"\*\&\$\#\+\@]+')

def split_on_sep(tensor, sep, dim=-1, shapes=None):

    if len(tensor.size()) != 2:
        raise NotImplementedError(' split_on_sep: only split on 2-D tensors is supported for now. Thank you for your understanding :-)')
  
    if dim == 0:
        tensor = tensor.t()
    (bsz, t_len) = tensor.size() 
    sep_idx = (tensor == sep).nonzero()
    num_of_idx = int(sep_idx[:,-1].size(0) / bsz)
    assert torch.sum(tensor == sep) == bsz * num_of_idx
    # Make a strong check
    tmplist = sep_idx[:,-1].tolist()
    idx_dict = {}
    for idx in tmplist:
        idx_dict[idx] = 1
    idxlist = list(idx_dict.keys())
    assert len(tmplist) == len(idxlist) * bsz

    split_idx = sep_idx[:,-1][:num_of_idx].tolist()
    split_idx.append(t_len)

    if sep_idx.numel() > 0:
        res = []
        sh_flag = False
        if shapes is not None:
            sh_flag = True
            assert len(split_idx) == shapes.size(0)
        for i in range(len(split_idx)):
            start=0 if i == 0 else split_idx[i-1]+1
            split_tsr = torch.index_select( tensor, 1, torch.LongTensor(range(start,split_idx[i])).to(tensor.device) )
            if dim == 0:
                split_tsr = split_tsr.t()
            if sh_flag: 
                split_tsr = split_tsr[:shapes[i,0],:shapes[i,1]]
            res.append( split_tsr )
        return res
    else:
        return [tensor]

def concat_with_sep(tensors, sep, dim=-1, shapes=None):

    if dim > len(tensors[0].size())-1 or len(tensors[0].size()) > 2 or (not isinstance(tensors, list)): 
        raise ValueError

    if len(tensors) > 1:
        if shapes is not None:
            max_shapes = [torch.max(shapes[:,j], 0)[0].item() for j in range(shapes.size(1))]
        dims = max_shapes[:] if shapes is not None else list(tensors[0].size())
        dims[dim] = 1
 
        res_list = []
        for i in range(len(tensors)-1):
            if shapes is not None:
                app_t = torch.LongTensor( torch.Size(max_shapes) ).to(tensors[i])
                app_t[:tensors[i].size(0),:tensors[i].size(1)] = tensors[i]
            else:
                app_t = tensors[i]

            res_list.append( app_t )
            res_list.append( torch.Tensor(torch.Size(dims)).to(tensors[0]).fill_(sep) )
        res_list.append( tensors[-1] )

        return torch.cat( res_list, dim)
    else:
        return tensors[0]

def copy_tensor_for_collate(src, dst, bos_idx=None, eos_idx=None, move_trail=False):
    assert dst.numel() == src.numel()
    if move_trail:
        if bos_idx is not None:
            assert src[0] == bos_idx
            dst[-1] = bos_idx
            dst[:-1] = src[1:]
        else:
            assert src[-1] == eos_idx
            dst[0] = eos_idx
            dst[1:] = src[:-1]
    else:
        dst.copy_(src)

char_reduce = torch.sum

def char2token_features_(src, dims, bds, tk_sort, offset):
    
    (T, B, C) = dims
    total_offset = 2*offset if offset == 1 else offset
    bounds_offset = 0 if offset == 1 or offset == 0 else 1

    res = torch.zeros(T-total_offset, B, C).to(src)
    for i in range(B):
        bounds = bds[i]+bounds_offset 
        res[:bounds.size(0),i,:] = torch.stack( [char_reduce(src[bounds[bi,0]:bounds[bi,1],i,:], 0) for bi in range(bounds.size(0))] , 0 )

    return res

def get_chars_from_tokens_(tokens, t2c_map, mdict):

    (B, T) = tokens.size()
    assert T == 1
    for bi in range(B): 
        t = tokens[bi,0].item()
        if t in t2c_map:
            tmp = [t2c_map[t].to(tokens)]
        else:
            sys.stderr.write(' *** get_chars_from_tokens WARNING: predicted token {} ({}) is not defined in current map, backing off to <bos>\n'.format(t, mdict.string(tokens[bi,:]))) 
            tmp = [t2c_map[mdict.bos()].to(tokens)]
    max_len = max( [t.size(0) for t in tmp if len(t.size()) > 0] )
    if max_len == 0:
        max_len = 1
    res = torch.LongTensor(B, max_len).fill_(mdict.pad()).to(tokens)
    for bi in range(B):
        bound = tmp[bi].size(0) if len(tmp[bi].size()) > 0 else 1
        res[bi,:bound] = tmp[bi]
    return res

