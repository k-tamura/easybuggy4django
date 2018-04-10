import datetime
import os
import tempfile
import threading
import time
from time import sleep
from django.template.defaultfilters import filesizeformat

import numpy as np
import psutil
from PIL import Image, ImageOps
from django import forms
from django.conf import settings
from django.db import transaction, connection
from django.shortcuts import render, redirect
from django.utils.translation import ugettext as _

from .forms import UploadFileForm
from .models import User

a = []

a_lock = threading.Lock()
b_lock = threading.Lock()
switch_flag = True

file_refs = []

def index(request):
    d = {'title': 'EasyBuggy Django'}
    if 'dlpinit' in request.session:
        del request.session['dlpinit']
    return render(request, 'index.html', d)


def deadlock(request):
    d = {
        'title': _('title.deadlock.page'),
        'msg': _('msg.dead.lock.not.occur'),
        'note': _('msg.note.deadlock'),
    }
    if 'dlpinit' not in request.session:
        request.session['dlpinit'] = "True"
    else:
        global switch_flag
        if switch_flag:
            with a_lock:
                print("Locked a_lock.")
                switch_flag = False
                sleep(5)
                with b_lock:
                    print("Locked a_lock. -> Locked b_lock.")
        else:
            with b_lock:
                print("Locked b_lock.")
                switch_flag = True
                sleep(5)
                with a_lock:
                    print("Locked b_lock. -> Locked a_lock.")
    return render(request, 'deadlock.html', d)


def deadlock2(request):
    d = {
        'title': _('title.deadlock2.page'),
        'note': _('msg.note.deadlock2'),
    }
    order = get_order(request)
    if request.method == 'POST':
        with transaction.atomic():
            number = 0
            while True:
                number += 1
                uid = request.POST.get("uid_" + str(number))
                if uid is None:
                    break
                user = User.objects.get(id=uid)
                user.name = request.POST.get(uid + "_name")
                user.phone = request.POST.get(uid + "_phone")
                user.mail = request.POST.get(uid + "_mail")
                user.save()
                sleep(1)

    d['users'] = User.objects.raw("SELECT * FROM easybuggy_user WHERE ispublic = 'true' ORDER BY id " + order)
    d['order'] = order
    return render(request, 'deadlock2.html', d)


def infiniteloop(request):
    i = 1
    while 0 < i:
        i += 1


def redirectloop(request):
    return redirect("/redirectloop")


def memoryleak(request):
    leak_memory()
    d = {
        'title': _('title.memoryleak.page'),
        'note': _('msg.note.memoryleak'),
    }
    try:
        ps = psutil.Process(os.getpid())
        mem = ps.memory_full_info()
        d = {
            'title': _('title.memoryleak.page'),
            'note': _('msg.note.memoryleak'),
            'pid': ps.pid,
            'rss': convert_bytes(mem.rss),
            'pcnt_rss': round(ps.memory_percent(memtype='rss'), 2),
            # 'vms': mem.vms,
            # 'shared': mem.shared,
            # 'text': mem.text,
            # 'lib': mem.lib,
            # 'data': mem.data,
            # 'dirty': mem.dirty,
            'uss': convert_bytes(mem.uss),
            'pcnt_uss': round(ps.memory_percent(memtype='uss'), 2),
            'pss': convert_bytes(mem.pss),
            'pcnt_pss': round(ps.memory_percent(memtype='pss'), 2),
            'swap': convert_bytes(mem.swap),
            'info': ps.as_dict(attrs=["cmdline", "username"]),
        }
    except psutil.AccessDenied:
        pass
    except psutil.NoSuchProcess:
        pass
    return render(request, 'memoryleak.html', d)


# TODO This function cannot leak connections
# See also: https://stackoverflow.com/questions/24661754/necessity-of-explicit-cursor-close
def dbconnectionleak(request):
    d = {
        'title': _('title.dbconnectionleak.page'),
        'note': _('msg.note.dbconnectionleak'),
    }
    c = connection.cursor()
    try:
        c.execute("SELECT id, name, phone, mail FROM easybuggy_user WHERE ispublic = 'true' ORDER BY id asc")
        d['users'] = c.fetchall()
    finally:
        # c.close()
        pass
    return render(request, 'dbconnectionleak.html', d)


def filedescriptorleak(request):
    d = {
        'title': _('title.filedescriptorleak.page'),
        'note': _('msg.note.filedescriptorleak'),
    }
    global file_refs
    temp_file = os.path.join(tempfile._get_default_tempdir(), 'history.csv')
    try:
        f = open(temp_file, 'a')
        f.write(str(datetime.datetime.now()) + ',' + get_client_ip(request) + ',' + request.session.session_key + '\n')
        f.flush()
    finally:
        f.close()
    try:
        f = open(temp_file, 'r')
        history = []
        i = 0
        for row in f:
            i += 1
            history.append(row.split(','))
        del history[:len(history) - 15]
        d['history'] = reversed(history)
        file_refs.append(f)  # TODO remove if possible
    finally:
        # f.close()
        pass
    return render(request, 'filedescriptorleak.html', d)


def commandinjection(request):
    d = {
        'title': _('title.commandinjection.page'),
        'note': _('msg.note.commandinjection'),
    }
    if request.method == 'POST':
        address = request.POST.get("address")
        cmd = 'echo "This is for testing." | mail -s "Test Mail" -r from@example.com ' + address
        if os.system(cmd) == 0:
            d['result'] = _('msg.send.mail.success')
        else:
            d['result'] = _('msg.send.mail.failure')
    return render(request, 'commandinjection.html', d)


def iof(request):
    d = {
        'title': _('title.intoverflow.page'),
        'note': _('msg.note.intoverflow'),
    }
    if request.method == 'POST':
        str_times = request.POST.get("times")

        if str_times is not None and str_times is not '':
            times = int(str_times)
            if times >= 0:
                # TODO Change a better way
                thickness = int(np.array([2 ** times, ], dtype=int)) / 10  # mm
                thickness_m = int(thickness) / 1000  # m
                thickness_km = int(thickness_m) / 1000  # km

                d['description'] = times + 1

                if times >= 0:
                    d['times'] = str_times
                    description = str(thickness) + " mm"
                    if thickness_m is not None and thickness_km is not None:
                        if thickness_m >= 1 and thickness_km < 1:
                            description += " = " + str(thickness_m) + " m"
                        if thickness_km >= 1:
                            description += " = " + str(thickness_km) + " km"
                    if times == 42:
                        description += " : " + _('msg.answer.is.correct')
                    d['description'] = description

    return render(request, 'intoverflow.html', d)


def lotd(request):
    d = {
        'title': _('title.lossoftrailingdigits.page'),
        'note': _('msg.note.lossoftrailingdigits'),
    }
    if request.method == 'POST':
        number = request.POST["number"]
        d['number'] = number
        if number is not None and -1 < float(number) < 1:
            d['result'] = float(number) + 1
    return render(request, 'lossoftrailingdigits.html', d)


def roe(request):
    d = {
        'title': _('title.roundofferror.page'),
        'note': _('msg.note.roundofferror'),
    }
    if request.method == 'POST':
        number = request.POST["number"]
        d['number'] = number
        if number is not None and number is not "0" and number.isdigit():
            d['result'] = float(number) - 0.9
    return render(request, 'roundofferror.html', d)


def te(request):
    d = {
        'title': _('title.truncationerror.page'),
        'note': _('msg.note.truncationerror'),
    }
    if request.method == 'POST':
        number = request.POST["number"]
        d['number'] = number
        if number is not None and number is not "0" and number.isdigit():
            d['result'] = 10.0 / float(number)
    return render(request, 'truncationerror.html', d)


def xss(request):
    d = {
        'title': _('title.xss.page'),
        'msg': _('msg.enter.string'),
        'note': _('msg.note.xss'),
    }
    if request.method == 'POST':
        input_str = request.POST["string"]
        if input_str is not None:
            d['msg'] = input_str[::-1]

    return render(request, 'xss.html', d)


def sqlijc(request):
    d = {
        'title': _('title.sqlijc.page'),
        'note': _('msg.note.sqlijc'),
    }
    if request.method == 'POST':
        name = request.POST["name"]
        password = request.POST["password"]
        d['users'] = User.objects.raw("SELECT * FROM easybuggy_user WHERE ispublic = 'true' AND name='" + name +
                                      "' AND password='" + password + "' ORDER BY id")

    return render(request, 'sqlijc.html', d)


def unrestrictedsizeupload(request):
    d = {
        'title': _('title.unrestrictedsizeupload.page'),
        'note': _('msg.note.unrestrictedsizeupload'),
    }
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['file']
            handle_uploaded_file(uploaded_file)
            content_type = uploaded_file.content_type.split('/')[0]
            if content_type in settings.CONTENT_TYPES:
                # TODO This check is too late
                if uploaded_file._size > settings.MAX_UPLOAD_SIZE:
                    raise forms.ValidationError(_('Please keep filesize under %s. Current filesize %s') % (
                    filesizeformat(settings.MAX_UPLOAD_SIZE), filesizeformat(uploaded_file._size)))
                invert(uploaded_file)
                d['file_path'] = os.path.join("static", "uploadfiles", uploaded_file.name)
            else:
                d['errmsg'] = _('msg.not.image.file')
    else:
        form = UploadFileForm()
    d['form'] = form
    return render(request, 'unrestrictedsizeupload.html', d)


# -------- private method
def get_order(request):
    order = request.GET.get("order")
    if order == 'asc':
        order = 'desc'
    else:
        order = 'asc'
    return order


def leak_memory():
    global a
    for i in range(100000):
        a.append(time.time())


def convert_bytes(n):
    symbols = ('K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
    prefix = {}
    for i, s in enumerate(symbols):
        prefix[s] = 1 << (i + 1) * 10
    for s in reversed(symbols):
        if n >= prefix[s]:
            value = float(n) / prefix[s]
            return '%.1f%s' % (value, s)
    return "%sB" % n


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def handle_uploaded_file(f):
    # TODO change directory from "static" to another
    upload_dirs = os.path.join(settings.BASE_DIR, "static", "uploadfiles")
    if not os.path.exists(upload_dirs):
        os.mkdir(upload_dirs)
    temp_file = os.path.join(upload_dirs, f.name)
    with open(temp_file, 'wb+') as destination:
        for chunk in f.chunks():
            destination.write(chunk)


def invert(f):
    temp_file = os.path.join(settings.BASE_DIR, "static", "uploadfiles", f.name)
    im = Image.open(f).convert('RGB')
    im_invert = ImageOps.invert(im)
    im_invert.save(temp_file, quality=95)

