import datetime
import logging
import os
import re
import smtplib
import sys
import tempfile
import threading
import time
import traceback
import xml.sax
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from time import sleep
from validate_email import validate_email
import numpy as np
import psutil
import requests
from PIL import Image, ImageOps
from django import forms
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.backends import UserModel
from django.db import transaction, connection, DatabaseError, OperationalError
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.template.defaultfilters import filesizeformat
from django.utils.translation import ugettext as _
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from ldap3 import Server, Connection, ALL
from ldap3.core.exceptions import LDAPExceptionError

from .forms import UploadFileForm
from .models import User
from .uploadhandler import QuotaUploadHandler

logger = logging.getLogger('easybuggy')

# TODO change directory from "static" to another
UPLOAD_DIR = os.path.join(settings.BASE_DIR, "static", "uploadfiles")

a_lock = threading.Lock()
b_lock = threading.Lock()
switch_flag = True

memory_refs = []
file_refs = []
netsocket_refs = []

# Dictionary for in-memory account locking
all_users_login_history = {}


def index(request):
    d = {
        'title': 'EasyBuggy Django',
        'isOnlyVulnerabilities': settings.IS_ONLY_VULNERABILITIES,
    }
    if 'dlpinit' in request.session:
        del request.session['dlpinit']

    return render(request, 'index.html', d)


def ping(request):
    return HttpResponse("It works!")


# -----------------------------------------------------------------------
# Authentication filter function
def redirect_login(request):
    # Login (authentication) is needed to access admin pages (under /admins).
    target = request.path
    login_type = request.GET.get("logintype")
    query_string = request.META['QUERY_STRING']

    # Remove "login_type" parameter from query string.
    if login_type is not None and query_string is not None:
        query_string = query_string.replace("logintype=" + login_type + "&", "")
        query_string = query_string.replace("&logintype=" + login_type, "")
        query_string = query_string.replace("logintype=" + login_type, "")
        if len(query_string) > 0:
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
# -----------------------------------------------------------------------


def main(request):
    if not request.user.is_authenticated:
        return redirect_login(request)
    d = {
        'title': _('title.adminmain.page'),
    }
    return render(request, 'adminmain.html', d)


def admins_logout(request):
    if request.user.is_authenticated:
        logout(request)
    return index(request)


def admins_login(request):
    if request.user.is_authenticated:
        return main(request)
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
                d['errmsg'] = _("msg.authentication.fail")
            else:
                user = authenticate(request, username=username, password=password)
                if user is not None:
                    login(request, user)
                    # authentication succeeded, then reset account lock
                    reset_account_lock(username)
                    request.session["username"] = username
                    if 'target' not in request.session:
                        return main(request)
                    else:
                        target = request.session['target']
                        del request.session['target']
                        return redirect(target)
                else:
                    d['errmsg'] = _("msg.authentication.fail")

                # account lock count +1
                increment_account_lock_num(username)

        return render(request, 'login.html', d)


def deadlock(request):
    d = {
        'title': _('title.deadlock.page'),
        'note': _('msg.note.deadlock'),
    }
    if 'dlpinit' not in request.session:
        # Bypass deadlock logic if accessing from index page
        request.session['dlpinit'] = "True"
    else:
        # ----------------------------------------------------------
        # Logic that deadlock occurs if multiple threads access within five seconds
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
        # ----------------------------------------------------------

    # Get stacktraces of deadlock threads
    stack_traces = []
    for tid, stack in sys._current_frames().items():
        stack_trace = str(traceback.format_stack(stack))
        if stack_trace.find('with a_lock') >= 0 or stack_trace.find('with b_lock') >= 0:
            stack_traces.append(traceback.extract_stack(stack))

    if len(stack_traces) >= 2:
        d['stack_traces'] = stack_traces
        d['msg'] = _('msg.dead.lock.detected')
    else:
        d['msg'] = _('msg.dead.lock.not.occur')
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
                    uid = request.POST.get("uid_" + str(number + 1))
                    if uid is None:
                        break
                    number += 1
                    user = User.objects.get(id=uid)
                    user.name = request.POST.get(uid + "_name")
                    user.phone = request.POST.get(uid + "_phone")
                    user.mail = request.POST.get(uid + "_mail")
                    user.save()
                    logger.info(uid + " is updated.")
                    sleep(1)
                d['msg'] = _('msg.update.records') % {'count': number}
            except OperationalError as op_err:
                logger.exception('OperationalError occurs: %s', op_err)
                d['errmsg'] = _('msg.deadlock.occurs')
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
        d['pid'] = ps.pid
        d['rss'] = convert_bytes(mem.rss)
        d['pcnt_rss'] = round(ps.memory_percent(memtype='rss'), 2)
        d['uss'] = convert_bytes(mem.uss)
        d['pcnt_uss'] = round(ps.memory_percent(memtype='uss'), 2)
        d['info'] = ps.as_dict(attrs=["cmdline", "username"])

        if os.name == 'posix':
            d['pss'] = convert_bytes(mem.pss)
            d['pcnt_pss'] = round(ps.memory_percent(memtype='pss'), 2)
            d['swap'] = convert_bytes(mem.swap)
    except psutil.AccessDenied:
        pass
    except psutil.NoSuchProcess:
        pass
    return render(request, 'memoryleak.html', d)


def network_socket_leak(request):
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
            netsocket_refs.append(response)  # TODO remove if possible
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
def db_connection_leak(request):
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


def file_descriptor_leak(request):
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


def thread_leak(request):
    d = {
        'title': _('title.threadleak.page'),
        'note': _('msg.note.threadleak'),
    }
    t1 = threading.Thread(target=active_threads_count, name="atc")
    t1.start()
    d['count'] = threading.active_count()
    return render(request, 'threadleak.html', d)


def mojibake(request):
    d = {
        'title': _('title.mojibake.page'),
        'msg': _('msg.enter.string'),
        'note': _('msg.note.mojibake'),
    }
    if request.method == 'POST':
        request.encoding = 'ISO-8859-1'
        input_str = request.POST.get("string")
        if input_str is not None:
            d['msg'] = input_str.title()
    return render(request, 'mojibake.html', d)


def integer_overflow(request):
    d = {
        'title': _('title.intoverflow.page'),
        'note': _('msg.note.intoverflow'),
    }
    if request.method == 'POST':
        str_times = request.POST.get("times")

        if str_times is not None and str_times is not '' and str_times.isdigit():
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
                        if 1 <= thickness_m and thickness_km < 1:
                            description += " = " + str(thickness_m) + " m"
                        if 1 <= thickness_km:
                            description += " = " + str(thickness_km) + " km"
                    if times == 42:
                        description += " : " + _('msg.answer.is.correct')
                    d['description'] = description

    return render(request, 'intoverflow.html', d)


def round_off_error(request):
    d = {
        'title': _('title.roundofferror.page'),
        'note': _('msg.note.roundofferror'),
    }
    if request.method == 'POST':
        number = request.POST.get("number")
        if number is not None and number is not "0" and number.isdigit():
            d['number'] = number
            d['result'] = float(number) - 0.9
    return render(request, 'roundofferror.html', d)


def truncation_error(request):
    d = {
        'title': _('title.truncationerror.page'),
        'note': _('msg.note.truncationerror'),
    }
    if request.method == 'POST':
        number = request.POST.get("number")
        if number is not None and number is not "0" and number.isdigit():
            d['number'] = number
            d['result'] = 10.0 / float(number)
    return render(request, 'truncationerror.html', d)


def loss_of_trailing_digits(request):
    d = {
        'title': _('title.lossoftrailingdigits.page'),
        'note': _('msg.note.lossoftrailingdigits'),
    }
    if request.method == 'POST':
        number = request.POST.get("number")
        if number is not None and is_number(number) and -1 < float(number) < 1:
            d['number'] = number
            d['result'] = float(number) + 1
    return render(request, 'lossoftrailingdigits.html', d)


def xss(request):
    d = {
        'title': _('title.xss.page'),
        'msg': _('msg.enter.string'),
        'note': _('msg.note.xss'),
    }
    if request.method == 'POST':
        input_str = request.POST.get("string")
        if input_str is not None and input_str is not '':
            d['msg'] = input_str[::-1]
    return render(request, 'xss.html', d)


def sql_injection(request):
    d = {
        'title': _('title.sqlijc.page'),
        'note': _('msg.note.sqlijc'),
    }
    if request.method == 'POST':
        name = request.POST.get("name")
        password = request.POST.get("password")
        d['users'] = User.objects.raw("SELECT * FROM easybuggy_user WHERE ispublic = 'true' AND name='" + name +
                                      "' AND password='" + password + "' ORDER BY id")
    return render(request, 'sqlijc.html', d)


def ldap_injection(request):
    if request.user.is_authenticated:
        return main(request)
    else:
        d = {
            'title': _('title.login.page'),
            'note': _('msg.note.ldap.injection'),
        }
        if request.method == 'GET':
            return render(request, 'login.html', d)
        elif request.method == 'POST':
            username = request.POST.get("username")
            password = request.POST.get("password")

            if is_account_lockedout(username):
                d['errmsg'] = _("msg.authentication.fail")
            else:
                try:
                    server = Server(settings.LDAP_HOST, settings.LDAP_PORT, get_info=ALL)
                    conn = Connection(server, 'uid=admin,ou=people,dc=t246osslab,dc=org', 'password', auto_bind=True)
                    conn.search('ou=people,dc=t246osslab,dc=org',
                                '(&(uid=' + username + ')(userPassword=' + password + '))',
                                attributes=['uid'])  # TODO trim
                    if len(conn.entries) > 0:
                        user = UserModel._default_manager.get_by_natural_key(conn.entries[0].uid)
                        login(request, user)
                        # authentication succeeded, then reset account lock
                        reset_account_lock(username)
                        request.session["username"] = username
                        if 'target' not in request.session:
                            return main(request)
                        else:
                            target = request.session['target']
                            del request.session['target']
                            return redirect(target)
                    else:
                        d['errmsg'] = _("msg.authentication.fail")
                        # account lock count +1
                        increment_account_lock_num(username)

                except LDAPExceptionError as le:
                    d['errmsg'] = _("msg.ldap.access.fail")
                except Exception as e:
                    logger.exception('Exception occurs: %s', e)
                    d['errmsg'] = _('msg.unknown.exception.occur') + ": " + str(e)

        return render(request, 'login.html', d)


def code_injection(request):
    d = {
        'title': _('title.codeinjection.page'),
        'note': _('msg.note.codeinjection'),
    }
    if request.method == 'POST':
        expression = request.POST.get('expression', '')
        if expression is not None and expression is not '':
            d['expression'] = expression
            expression = expression.replace("math", "__import__('math')")
            try:
                d['value'] = str(eval(expression))
            except Exception as e:
                logger.exception('Exception occurs: %s', e)
                d['errmsg'] = _("msg.invalid.expression") % {"exception": e}
            finally:
                pass
    return render(request, 'codeinjection.html', d)


def command_injection(request):
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
            d['errmsg'] = _('msg.send.mail.failure')
    return render(request, 'commandinjection.html', d)


def mail_header_injection(request):
    d = {
        'title': _('title.mailheaderinjection.page'),
        'note': _('msg.note.mailheaderinjection'),
    }

    if request.method == 'POST':

        name = request.POST.get("name")
        mail = request.POST.get("mail")
        subject = request.POST.get("subject")
        content = request.POST.get("content")

        if not subject or subject is None or not content or content is None:
            d['errmsg'] = _('msg.mail.is.empty')
            return render(request, 'mailheaderinjection.html', d)

        msg_body = _('label.name') + ': ' + name + '<br>' + _('label.mail') + ': ' + mail + '<br><br>' + _(
            'label.content') + ': ' + content + '<br>'

        try:
            send_email(subject, msg_body)
            d['msg'] = _("msg.sent.mail")
        except Exception as e:
            logger.exception('Exception occurs: %s', e)
            d['errmsg'] = _('msg.unknown.exception.occur')

    return render(request, 'mailheaderinjection.html', d)


def unrestricted_size_upload(request):
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
                if settings.MAX_UPLOAD_SIZE < uploaded_file._size:
                    raise forms.ValidationError('Please keep filesize under %s. Current filesize %s' % (
                        filesizeformat(settings.MAX_UPLOAD_SIZE), filesizeformat(uploaded_file._size)))
                try:
                    invert(uploaded_file)
                except Exception as e:
                    logger.exception('Exception occurs: %s', e)
                    d['errmsg'] = _('msg.reverse.color.fail')
                else:
                    d['file_path'] = os.path.join("static", "uploadfiles", uploaded_file.name)
                    d['msg'] = _('msg.reverse.color.complete')
                    del d['note']
            else:
                d['errmsg'] = _('msg.not.image.file')
    else:
        form = UploadFileForm()
    d['form'] = form
    return render(request, 'unrestrictedsizeupload.html', d)


@csrf_exempt
def unrestricted_extension_upload(request):
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
            try:
                grayscale(uploaded_file)
            except Exception as e:
                logger.exception('Exception occurs: %s', e)
                d['errmsg'] = _('msg.convert.grayscale.fail')
            else:
                d['file_path'] = os.path.join("static", "uploadfiles", uploaded_file.name)
                d['msg'] = _('msg.convert.grayscale.complete')
                del d['note']
    else:
        form = UploadFileForm()
    d['form'] = form
    return render(request, 'unrestrictedextupload.html', d)


def brute_force(request):
    if request.user.is_authenticated:
        return main(request)
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
                if 'target' not in request.session:
                    return main(request)
                else:
                    target = request.session['target']
                    del request.session['target']
                    return redirect(target)
            else:
                d['errmsg'] = _("msg.authentication.fail")

        return render(request, 'login.html', d)


def open_redirect(request):
    if request.user.is_authenticated:
        return main(request)
    else:
        d = {
            'title': _('title.login.page'),
            'note': _('msg.note.open.redirect'),
        }
        if request.method == 'GET':
            return render(request, 'login.html', d)
        elif request.method == 'POST':
            username = request.POST.get("username")
            password = request.POST.get("password")

            if is_account_lockedout(username):
                d['errmsg'] = _("msg.authentication.fail")
            else:
                user = authenticate(request, username=username, password=password)
                if user is not None:
                    login(request, user)
                    # authentication succeeded, then reset account lock
                    reset_account_lock(username)
                    request.session["username"] = username
                    if "goto" in request.GET:
                        return redirect(request.GET.get("goto"))
                    else:
                        if 'target' not in request.session:
                            return main(request)
                        else:
                            target = request.session['target']
                            del request.session['target']
                            return redirect(target)
                else:
                    d['errmsg'] = _("msg.authentication.fail")

                # account lock count +1
                increment_account_lock_num(username)

        return render(request, 'login.html', d)


def verbose_message(request):
    if request.user.is_authenticated:
        return main(request)
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
                d['errmsg'] = _("msg.account.locked") % {"count": settings.ACCOUNT_LOCK_COUNT}
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
                    if 'target' not in request.session:
                        return main(request)
                    else:
                        target = request.session['target']
                        del request.session['target']
                        return redirect(target)
                else:
                    d['errmsg'] = _("msg.password.not.match")

            # account lock count +1
            increment_account_lock_num(username)

        return render(request, 'login.html', d)


@csrf_exempt
def csrf(request):
    if not request.user.is_authenticated:
        return redirect_login(request)
    d = {
        'title': _('title.csrf.page'),
        'note': _('msg.note.csrf'),
    }
    if request.method == 'POST' and "username" in request.session:
        username = request.session["username"]
        password = request.POST.get("password")
        if password is not None and 8 <= len(password):
            try:
                from django.contrib.auth.models import User
                User.objects.filter(is_superuser=True)
                u = User.objects.get(username=username)
                u.set_password(password)
                u.save()
                d['complete'] = True
            except Exception as e:
                logger.exception('Exception occurs: %s', e)
                d['errmsg'] = _('msg.passwd.change.failed')
        else:
            d['errmsg'] = _('msg.passwd.is.too.short')
    return render(request, 'csrf.html', d)


@xframe_options_exempt
def clickjacking(request):
    if not request.user.is_authenticated:
        return redirect_login(request)
    d = {
        'title': _('title.clickjacking.page'),
        'note': _('msg.note.clickjacking'),
    }
    if request.method == 'POST' and "username" in request.session:
        username = request.session["username"]
        mail = request.POST.get("mail")
        if validate_email(mail):
            try:
                from django.contrib.auth.models import User
                User.objects.filter(is_superuser=True)
                u = User.objects.get(username=username)
                u.email = mail
                u.save()
                d['complete'] = True
            except Exception as e:
                logger.exception('Exception occurs: %s', e)
                d['errmsg'] = _('msg.mail.change.failed')
        else:
            d['errmsg'] = _('msg.mail.format.is.invalid')
    return render(request, 'clickjacking.html', d)


@csrf_exempt
def xxe(request):
    request.upload_handlers.insert(0, QuotaUploadHandler())
    d = {
        'title': _('title.xxe.page'),
        'note': _('msg.note.xxe'),
    }
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['file']
            content_type = uploaded_file.content_type
            if content_type == "text/xml":
                str_text = ''
                for line in uploaded_file:
                    str_text = str_text + line.decode()
                obj = MyObject()
                parser = MyContentHandler(obj)
                xml.sax.parseString(str_text, parser)
                d['results'] = parser.results
            else:
                d['errmsg'] = _('msg.not.xml.file')
    else:
        form = UploadFileForm()
    d['form'] = form
    d['normal_xml'] = '<people>\n' \
                      '    <person>\n' \
                      '        <id>user00</id>\n' \
                      '        <name>Mark</name>\n' \
                      '        <phone>090-9999-8888</phone>\n' \
                      '        <mail>Mark@gmail.com</mail>\n' \
                      '    </person>\n' \
                      '    <person>\n' \
                      '        <id>user01</id>\n' \
                      '        <name>David</name>\n' \
                      '        <phone>090-6666-8888</phone>\n' \
                      '        <mail>David@gmail.com</mail>\n' \
                      '    </person>\n' \
                      '</people>'
    d['xxe_xml'] = '<!DOCTYPE person [<!ENTITY param SYSTEM "file:///etc/passwd">]>\n' \
                   '<person>\n' \
                   '<id>&param;</id>\n' \
                   '</person>'
    return render(request, 'xxe.html', d)


# -------- private method
def active_threads_count():
    while True:
        logger.info("Current thread count: " + str(threading.active_count()))
        sleep(100)


def get_order(request):
    order = request.GET.get("order")
    if order == 'asc':
        order = 'desc'
    else:
        order = 'asc'
    return order


def leak_memory():
    for i in range(100000):
        memory_refs.append(time.time())


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
           and settings.ACCOUNT_LOCK_COUNT <= user_login_history[0] \
           and ((datetime.datetime.now() - user_login_history[1]).seconds < settings.ACCOUNT_LOCK_TIME)


def is_user_exist(username):
    from django.contrib.auth.models import User
    if User.objects.filter(username=username).exists():
        return True
    return False


# Python smtplib's mail header injection vulnerability has been fixed by the following commit:
# https://github.com/python/cpython/commit/5b2d9ddf69cecfb9ad4e687fab3f34ecc5a9ea4f#diff-7d35ae5e9e22a15ee979f1cba58bc60a
# However, the following bug has not been fixed in smtplib (Python) 3.6, so it may cause the security issue depending
# on mail server that does not correctly implement RFC, such as smtp-mail.outlook.com:
# https://bugs.python.org/issue32606
def send_email(subject, msg_body):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = settings.MAIL_USER
    msg['To'] = settings.MAIL_ADMIN_ADDRESS
    msg.attach(MIMEText(msg_body, 'plain'))

    smtp_server = smtplib.SMTP(settings.MAIL_SMTP_HOST, port=settings.MAIL_SMTP_PORT)
    if settings.MAIL_SMTP_STARTTLS_ENABLE:
        smtp_server.starttls()
    if settings.MAIL_SMTP_AUTH:
        smtp_server.login(settings.MAIL_USER, settings.MAIL_PASSWORD)

    smtp_server.sendmail(settings.MAIL_USER, settings.MAIL_ADMIN_ADDRESS, msg.as_string())


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


class MyObject:
    def __init__(self):
        self.id = None
        self.name = None
        self.phone = None
        self.mail = None

    def __repr__(self):
        return "%s (%s, %s, %s)" % (self.id, self.name, self.phone, self.mail)


class MyContentHandler(xml.sax.ContentHandler):
    def __init__(self, object):
        xml.sax.ContentHandler.__init__(self)
        self.object = object
        self.results = []

    def startElement(self, name, attrs):
        self.chars = ""

    def endElement(self, name):
        if name == "id":
            self.object.id = self.chars
        elif name == "name":
            self.object.name = self.chars
        elif name == "phone":
            self.object.phone = self.chars
        elif name == "mail":
            self.object.mail = self.chars
        elif name == "person":
            if self.object.id is not None:
                try:
                    user = User.objects.get(id=self.object.id)
                    user.name = self.object.name
                    user.phone = self.object.phone
                    user.mail = self.object.mail
                    user.save()
                    logger.info(self.object.id + " is updated.")
                    self.results.append(self.object.id + " is updated.")
                except User.DoesNotExist:
                    logger.info(self.object.id + " does not exist.")
                    self.results.append(self.object.id + " does not exist.")
                except DatabaseError as db_err:
                    logger.exception('DatabaseError occurs: %s', db_err)
                    raise db_err
                except Exception as e:
                    logger.exception('Exception occurs: %s', e)
                    raise e

    def characters(self, content):
        self.chars += content
