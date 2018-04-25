import datetime
import logging
import os
import re
import tempfile
import threading
import time
from time import sleep

import numpy as np
import psutil
import requests
from PIL import Image, ImageOps
from django import forms
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.db import transaction, connection, DatabaseError
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.template.defaultfilters import filesizeformat
from django.utils.translation import ugettext as _
from django.views.decorators.csrf import csrf_exempt

from easybuggy4django.easybuggy.uploadhandler import QuotaUploadHandler
from .forms import UploadFileForm
from .models import User

logger = logging.getLogger('easybuggy')

# TODO change directory from "static" to another
UPLOAD_DIR = os.path.join(settings.BASE_DIR, "static", "uploadfiles")

a = []

a_lock = threading.Lock()
b_lock = threading.Lock()
switch_flag = True

file_refs = []
netsockets_refs = []

all_users_login_history = {}


def index(request):
    d = {'title': 'EasyBuggy Django'}
    if 'dlpinit' in request.session:
        del request.session['dlpinit']
    return render(request, 'index.html', d)


def ping(request):
    return HttpResponse("It works!")


def admins(request):
    # Login (authentication) is needed to access admin pages (under /admins).
    if not request.user.is_authenticated:
        target = request.path
        login_type = request.GET.get("logintype")
        query_string = request.META['QUERY_STRING']

        # Remove "login_type" parameter from query string.
        if login_type is not None and query_string is not None:
            query_string = query_string.replace("logintype=" + login_type + "&", "")
            query_string = query_string.replace("&logintype=" + login_type, "")
            query_string = query_string.replace("logintype=" + login_type, "")
            if (len(query_string) > 0):
                query_string = "?" + query_string

        # Not authenticated yet
        request.session['target'] = target

        if login_type is None:
            # TODO for session fixation
            # redirect(response.encodeRedirectURL("/login" + query_string))
            return redirect("/login" + query_string)
        # elif "sessionfixation".equals(login_type):
        #    redirect(response.encodeRedirectURL("/" + login_type + "/login" + query_string))
        else:
            return redirect("/" + login_type + "/login" + query_string)
    else:
        d = {
            'title': _('title.adminmain.page'),
        }
        return render(request, 'adminmain.html', d)


def admins_logout(request):
    logout(request)
    return index(request)


def admins_login(request):
    if request.user.is_authenticated:
        return redirect("/admins/main")
    else:
        d = {
            'title': _('title.login.page'),
        }
        if request.method == 'GET':
            return render(request, 'login.html', d)
        elif request.method == 'POST':
            username = request.POST.get("username")
            password = request.POST.get("password")

            if is_account_lockedout(username):
                d['errmsg'] = _("msg.account.locked")
            else:
                user = authenticate(request, username=username, password=password)
                if user is not None:
                    login(request, user)
                    # authentication succeeded, then reset account lock
                    reset_account_lock(username)
                    request.session["username"] = username
                    target = request.POST.get("target")
                    if target is None:
                        return redirect("/admins/main")
                    else:
                        del request.session['target']
                        return redirect(target)
                else:
                    d['errmsg'] = _("msg.authentication.fail")

                # account lock count +1
                increment_account_lock_num(username)

        return render(request, 'login.html', d)


def bruteforce(request):
    if request.user.is_authenticated:
        return redirect("/admins/main")
    else:
        d = {
            'title': _('title.login.page'),
            'note': _('msg.note.brute.force'),
        }
        if request.method == 'GET':
            return render(request, 'login.html', d)
        elif request.method == 'POST':
            username = request.POST.get("username")
            password = request.POST.get("password")
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                request.session["username"] = username
                target = request.POST.get("target")
                if target is None:
                    return redirect("/admins/main")
                else:
                    del request.session['target']
                    return redirect(target)
            else:
                d['errmsg'] = _("msg.authentication.fail")

        return render(request, 'login.html', d)


def verbosemsg(request):
    if request.user.is_authenticated:
        return redirect("/admins/main")
    else:
        d = {
            'title': _('title.login.page'),
            'note': _('msg.note.verbose.errror.message'),
        }
        if request.method == 'GET':
            return render(request, 'login.html', d)
        elif request.method == 'POST':
            username = request.POST.get("username")
            password = request.POST.get("password")

            if is_account_lockedout(username):
                d['errmsg'] = _("msg.account.locked")
            elif not is_user_exist(username):
                d['errmsg'] = _("msg.user.not.exist")
            elif not bool(re.match("[0-9a-z]{8}", password)):
                d['errmsg'] = _("msg.low.alphnum8")
            else:
                user = authenticate(request, username=username, password=password)
                if user is not None:
                    login(request, user)
                    # authentication succeeded, then reset account lock
                    reset_account_lock(username)
                    request.session["username"] = username
                    target = request.POST.get("target")
                    if target is None:
                        return redirect("/admins/main")
                    else:
                        del request.session['target']
                        return redirect(target)
                else:
                    d['errmsg'] = _("msg.password.not.match")

            # account lock count +1
            increment_account_lock_num(username)

        return render(request, 'login.html', d)


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
                logger.info("Locked a_lock.")
                switch_flag = False
                sleep(5)
                with b_lock:
                    logger.info("Locked a_lock. -> Locked b_lock.")
        else:
            with b_lock:
                logger.info("Locked b_lock.")
                switch_flag = True
                sleep(5)
                with a_lock:
                    logger.info("Locked b_lock. -> Locked a_lock.")
    return render(request, 'deadlock.html', d)


def deadlock2(request):
    d = {
        'title': _('title.deadlock2.page'),
        'note': _('msg.note.deadlock2'),
    }
    order = get_order(request)
    if request.method == 'POST':
        with transaction.atomic():
            try:
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
                    logger.info(uid + " is updated.")
                    sleep(1)
            except DatabaseError as db_err:
                logger.exception('DatabaseError occurs: %s', db_err)
                raise db_err
            except Exception as e:
                logger.exception('Exception occurs: %s', e)
                raise e

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


def netsocketleak(request):
    d = {
        'title': _('title.netsocketleak.page'),
        'note': _('msg.note.netsocketleak'),
    }
    start = datetime.datetime.now()
    ping_url = request.GET.get("pingurl")
    if ping_url is None:
        ping_url = request.scheme + "://localhost:" + request.META['SERVER_PORT'] + "/ping"
    try:
        response = requests.get(ping_url)
        # req = urllib.request.Request(ping_url, headers={'Connection': 'KeepAlive'})
        # res = urllib.request.urlopen(req)
        try:
            # d['response_code'] = res.getcode()
            d['response_code'] = response.status_code
            d['ping_url'] = ping_url
            d['response_time'] = datetime.datetime.now() - start
            netsockets_refs.append(response)  # TODO remove if possible
        finally:
            # res.close()
            # response.close() # This line may not work if using requests 2.1.0 or earlier due to https://github.com/requests/requests/issues/1973
            pass
    except Exception as e:
        logger.exception('Exception occurs: %s', e)
        d['errmsg'] = _('msg.unknown.exception.occur') + ": " + str(e)
    return render(request, 'netsocketleak.html', d)


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
    except Exception as e:
        logger.exception('Exception occurs: %s', e)
    finally:
        # c.close()
        pass
    return render(request, 'dbconnectionleak.html', d)


def filedescriptorleak(request):
    d = {
        'title': _('title.filedescriptorleak.page'),
        'note': _('msg.note.filedescriptorleak'),
    }

    temp_file = os.path.join(tempfile._get_default_tempdir(), 'history.csv')
    try:
        f = open(temp_file, 'a')
        try:
            f.write(
                str(datetime.datetime.now()) + ',' + get_client_ip(request) + ',' + request.session.session_key + '\n')
            f.flush()
        finally:
            f.close()
    except Exception as e:
        logger.exception('Exception occurs: %s', e)
    finally:
        pass
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
    except Exception as e:
        logger.exception('Exception occurs: %s', e)
    finally:
        # f.close()
        pass
    return render(request, 'filedescriptorleak.html', d)


def threadleak(request):
    d = {
        'title': _('title.threadleak.page'),
        'note': _('msg.note.threadleak'),
    }
    t1 = threading.Thread(target=active_threads_count, name="atc")
    t1.start()
    d['count'] = threading.active_count()
    return render(request, 'threadleak.html', d)


def active_threads_count():
    while True:
        logger.info("Current thread count: " + str(threading.active_count()))
        sleep(100)


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


@csrf_exempt
def unrestrictedextupload(request):
    request.upload_handlers.insert(0, QuotaUploadHandler())
    d = {
        'title': _('title.unrestrictedextupload.page'),
        'note': _('msg.note.unrestrictedextupload'),
    }
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['file']
            handle_uploaded_file(uploaded_file)
            grayscale(uploaded_file)
            d['file_path'] = os.path.join("static", "uploadfiles", uploaded_file.name)
    else:
        form = UploadFileForm()
    d['form'] = form
    return render(request, 'unrestrictedextupload.html', d)


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
                # This size check is too late
                if uploaded_file._size > settings.MAX_UPLOAD_SIZE:
                    raise forms.ValidationError('Please keep filesize under %s. Current filesize %s' % (
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
    with open(get_uploaded_file(f), 'wb+') as destination:
        for chunk in f.chunks():
            destination.write(chunk)


def get_uploaded_file(f):
    if not os.path.exists(UPLOAD_DIR):
        os.mkdir(UPLOAD_DIR)
    return os.path.join(UPLOAD_DIR, f.name)


def invert(f):
    im = Image.open(f).convert('RGB')
    im_invert = ImageOps.invert(im)
    im_invert.save(get_uploaded_file(f))


def grayscale(f):
    im = Image.open(f)
    im_convert = ImageOps.grayscale(im)
    im_convert.save(get_uploaded_file(f))


def increment_account_lock_num(username):
    if username in all_users_login_history:
        user_login_history = all_users_login_history[username]
        user_login_history[0] = user_login_history[0] + 1
        user_login_history[1] = datetime.datetime.now()
    else:
        user_login_history = [1, datetime.datetime.now()]
        all_users_login_history[username] = user_login_history


def reset_account_lock(username):
    all_users_login_history[username] = [0, None]


def is_account_lockedout(username):
    if username is None or username not in all_users_login_history:
        return False
    user_login_history = all_users_login_history[username]
    return user_login_history[1] is not None \
           and user_login_history[0] == settings.ACCOUNT_LOCK_COUNT \
           and ((datetime.datetime.now() - user_login_history[1]).seconds < settings.ACCOUNT_LOCK_TIME)


def is_user_exist(username):
    from django.contrib.auth.models import User
    if User.objects.filter(username=username).exists():
        return True
    return False
