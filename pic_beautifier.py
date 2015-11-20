#!/usr/bin/env python
# -*- coding: utf-8 -*-
## pic_beautifier.py
## A helpful tool to beautify pictures
##
## This program is a free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, version 3 of the License.
##
## You can get a copy of GNU General Public License along this program
## But you can always get it from http://www.gnu.org/licenses/gpl.txt
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
import os
import re
import platform
from os import path
from PIL import Image
from PIL import ImageOps
from PIL import ImageEnhance
from datetime import datetime
from collections import OrderedDict
INI_FILE = 'beautifier.ini'


def fullpath(file, suffix='', base_dir=''):
    if base_dir:
        return ''.join([os.getcwd(), path.sep, base_dir, file, suffix])
    else:
        return ''.join([os.getcwd(), path.sep, file, suffix])


def readdata(file, base_dir=''):
    fp = fullpath(file, base_dir=base_dir)
    if not path.exists(fp):
        print("%s was not found." % fp)
    else:
        fr = open(fp, 'rU')
        try:
            return fr.read()
        finally:
            fr.close()
    return None


def dump(data, fname, mod='w'):
    fw = open(fname, mod)
    try:
        fw.write(data)
    finally:
        fw.close()


class enhancer:
# bright -> contrast -> sharpness -> crop -> transparent -> split -> shrink
    def __init__(self):
        self.__load_ini()
        arch = platform.architecture()
        if arch[1] == 'ELF':
            if '32' in arch[0]:
                self.__pngqt = path.sep.join(['.', 'bin', 'linux', 'x86', 'pngquant'])
            else:
                self.__pngqt = path.sep.join(['.', 'bin', 'linux', 'x64', 'pngquant'])
        else:
            self.__pngqt = path.sep.join(['.', 'bin', 'pngquant'])
        self.__usebin = path.exists(self.__pngqt)
        if self.__usebin and self.__prop['shrink']:
            print "use pngquant to shrink."

    def __load_ini(self):
        ini = readdata(INI_FILE)
        self.__eh_params = {'brightness': 0, 'contrast': 0, 'sharpness': 0}
        self.__prop = {'crop': 0, 'transparency': 0, 'shrink': 0, 'dump': 0}
        self.__padding = 0
        self.__skip = [0, 0, 0, 0]
        self.__cols = 1
        self.__threshold = 0xFF
        self.__io = {'in': None, 'out': None}
        for key in self.__eh_params:
            p = re.compile(''.join([r'(?:^|\n)\s*', key, r'\s*=\s*(\d(?:\.\d+)?)']), re.I)
            m = p.search(ini)
            if m:
                self.__eh_params[key] = float(m.group(1))
        for key in self.__prop:
            p = re.compile(''.join([r'(?:^|\n)\s*', key, r'\s*=\s*(yes|no)']), re.I)
            m = p.search(ini)
            if m:
                self.__prop[key] = 1 if m.group(1).lower()=='yes' else 0
        if self.__prop['crop']:
            cp_params = {}
            for key in ['padding', 'skipping']:
                p = re.compile(''.join([r'(?:^|\n)\s*', key, r'\s*=\s*([\d,]+)']), re.I)
                m = p.search(ini)
                if m:
                    cp_params[key] = m.group(1)
            if 'padding' in cp_params:
                padding = cp_params['padding'].strip(' ,').split(',')[0]
                if padding:
                    self.__padding = int(padding)
            if 'skipping' in cp_params:
                skipping = cp_params['skipping'].strip(' ,').split(',')
                for i in xrange(min(4, len(skipping))):
                    self.__skip[i] = int(skipping[i])
        p = re.compile(''.join([r'(?:^|\n)\s*split\s*=\s*([1-4])']), re.I)
        m = p.search(ini)
        if m:
            self.__cols = int(m.group(1))
        p = re.compile(''.join([r'(?:^|\n)\s*threshold\s*=\s*(2(?:[34][0-9]|5[0-5]))']), re.I)
        m = p.search(ini)
        if m:
            self.__threshold = int(m.group(1))
        for key in self.__io:
            p = re.compile(''.join([r'(?:^|\n)\s*', key, r'\s*=\s*([^\n]+)']), re.I)
            m = p.search(ini)
            if m:
                fp = m.group(1).strip()
                self.__io[key] = fp.rstrip(path.sep)

    def check_io_path(self):
        rst = False
        ip, op = self.__io['in'], self.__io['out']
        if ip and op:
            if not path.exists(op):
                os.makedirs(op)
            if not path.exists(ip):
                print "in-path is not exist."
            elif path.isfile(op) and path.isdir(ip):
                print "Out-path should be a folder if in-path is a folder."
            elif ip.lower() == op.lower():
                print "in-path is equal to out-path."
            elif path.isdir(ip) and op.lower().startswith(ip.lower()):
                print "Out-path cannot be a subfolder of the in-path."
            else:
                rst = True
        else:
            print "A pair of valid in-out paths are required."
        return rst

    def __enhance(self, img):
        if self.__eh_params['brightness']:
            enh = ImageEnhance.Brightness(img)
            img = enh.enhance(self.__eh_params['brightness'])
        if self.__eh_params['contrast']:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img = ImageOps.autocontrast(img)
            enh = ImageEnhance.Contrast(img)
            img = enh.enhance(self.__eh_params['contrast'])
        if self.__prop['transparency'] and not img.mode=='RGBA':
            img = img.convert('RGBA')
        if (self.__prop['crop'] or self.__cols>1) and not img.mode in ['RGB', 'RGBA']:
            img = img.convert('RGB')
        try:
            if self.__eh_params['sharpness']:
                enh = ImageEnhance.Sharpness(img)
                img = enh.enhance(self.__eh_params['sharpness'])
        except Exception, e:
            pass
        return img

    def __is_content(self, tri):
        trs = self.__threshold
        return tri[0]<trs or tri[1]<trs or tri[2]<trs

    def __checkV(self, h, v, pixels):
        for y in v:
            for x in h:
                if self.__is_content(pixels[x, y]):
                    return y

    def __checkH(self, h, v, pixels):
        for x in h:
            for y in v:
                if self.__is_content(pixels[x, y]):
                    return x

    def __crop(self, img):
        pixels = img.load()
        hb, vb, hmax, vmax = self.__skip[0], self.__skip[1], img.size[0]-self.__skip[2], img.size[1]-self.__skip[3]
        box = []
        for h, v in [(xrange(hb, hmax), xrange(vb, vmax)), (xrange(hmax-1, hb-1, -1), xrange(vmax-1, vb-1, -1))]:
            box.append(self.__checkH(h, v, pixels))
            box.append(self.__checkV(h, v, pixels))
        padding = self.__padding
        if padding:
            box[0] = hb if box[0]<padding else (box[0]-padding)
            box[1] = vb if box[1]<padding else (box[1]-padding)
            box[2] = (hmax-1) if (box[2]+padding>hmax-1) else (box[2]+padding)
            box[3] = (vmax-1) if (box[3]+padding>vmax-1) else (box[3]+padding)
        img = img.crop(box)
        return img

    def __erase_bg(self, img):
        pixels = img.load()
        for y in xrange(img.size[1]):
            for x in xrange(img.size[0]):
                if not self.__is_content(pixels[x, y]):
                    pixels[x, y] = (0xFF, 0xFF, 0xFF, 0)
        return img

    def __is_blank(self, h, v, pixels):
        for y in v:
            for x in h:
                if self.__is_content(pixels[x, y]):
                    return False
        return True

    def __split(self, img):
        pixels = img.load()
        hmax, vmax = img.size[0], img.size[1]
        x, hw, vw = 0, int(hmax/self.__cols), int(vmax/3)
        vs = int(vmax/80)
        vs = 10 if vs<10 else vs
        cols, xe = [], 0
        for i in xrange(self.__cols-1):
            x += hw
            xs, xe, ok = xe, x, False
            while xe < x+int(hw/30):
                if self.__is_blank(xrange(xe, xe+10), xrange(hw-vs, hw+vs), pixels) and\
                self.__is_blank(xrange(xe, xe+10), xrange(hw*2-vs, hw*2+vs), pixels):
                    ok = True
                    break
                else:
                    xe += 5
            if not ok:
                xe = x
                while xe > x-int(hw/30):
                    if self.__is_blank(xrange(xe, xe-10), xrange(hw-vs, hw+vs), pixels) and\
                    self.__is_blank(xrange(xe, xe-10), xrange(hw*2-vs, hw*2+vs), pixels):
                        ok = True
                        break
                    else:
                        xe -= 5
            if not ok:
                xe = x
            cols.append((xs, xe))
        imgs = []
        for xs, xe in cols:
            box = [xs, 0, xe, vmax-1]
            imgs.append(img.crop(box))
        imgs.append(img.crop((xe, 0, hmax-1, vmax-1)))
        return imgs

    def __save(self, img, file):
        if self.__usebin:
            img.save(file)
            os.system(''.join([self.__pngqt, ' -f --ext .png --quality 70-80 --speed=3 "', file, '" "', file, '"']))
        elif self.__prop['transparency'] or img.mode.endswith('A'):
            alpha = img.split()[-1]
            img = img.convert('P')
            mask = Image.eval(alpha, lambda a: 0xFF if a <=0x7F else 0)
            img.paste(0xFF, mask)
            img.save(file, transparency=0xFF)
        else:
            if not img.mode in ['1', 'L', 'P']:
                img = img.convert('P')
            img.save(file)

    def __process_single(self, inpath, outpath):
        dir, infile = path.split(inpath)
        name, ext = path.splitext(infile)
        ext = ext.lstrip(path.extsep)
        if re.compile(r'^(?:png|jpg|jpeg|gif|bmp|ico|tiff)$', re.I).search(ext.strip()):
            img = Image.open(inpath)
            img = self.__enhance(img)
            if self.__prop['crop']:
                img = self.__crop(img)
            if self.__prop['transparency']:
                img = self.__erase_bg(img)
                ext = 'png'
            if self.__cols > 1:
                imgs, sf = self.__split(img), '_%d'
            else:
                imgs, sf = [img], ''
            i, sfx = 0, ''
            for img in imgs:
                if sf:
                    i += 1
                    sfx = sf % i
                if path.isfile(outpath):
                    outfile = outpath
                elif dir.strip().lower() == outpath.strip().lower():
                    outfile = ''.join([dir, path.sep, name, '_new', sfx, path.extsep, ext])
                else:
                    inroot = self.__io['in']
                    if path.isdir(inroot):
                        dir = dir.replace(inroot, '', 1)
                        outpath = ''.join([outpath, dir])
                        if not path.exists(outpath):
                            os.makedirs(outpath)
                    outfile = ''.join([outpath, path.sep, name, sfx, path.extsep, ext])
                if self.__prop['dump']:
                    self.__imginfo[path.split(outfile)[1]] = img.size
                if ext.lower()=='png' and self.__prop['shrink']:
                    self.__save(img, outfile)
                else:
                    img.save(outfile)

    def beautify(self):
        imgpath, outpath = self.__io['in'], self.__io['out']
        if self.__prop['dump']:
            self.__imginfo = OrderedDict()
        if path.isfile(imgpath):
            self.__process_single(imgpath, outpath)
        else:
            dir, fname = path.split(imgpath)
            for root, dirs, files in os.walk(imgpath):
                for file in files:
                    self.__process_single(''.join([root, path.sep, file]), outpath)
        if self.__prop['dump']:
            if path.isfile(outpath):
                outpath = path.split(outpath)[0]
            infofile = path.sep.join([outpath, 'img_info.txt'])
            dump('\n'.join('\t'.join([k, str(v[0]), str(v[1])]) for k, v in self.__imginfo.iteritems()), infofile)


if __name__=="__main__":
    print "Start at %s" % datetime.now()
    if path.exists(fullpath(INI_FILE)):
        enh = enhancer()
        if enh.check_io_path():
            enh.beautify()
    else:
        print "%s was not found." % INI_FILE
    print "Finished at %s" % datetime.now()
    cmd = raw_input("Press Enter to exit...")
    if cmd:
        pass
