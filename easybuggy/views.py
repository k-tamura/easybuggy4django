from django.shortcuts import render, redirect
from django.utils.translation import ugettext as _
from django.db import transaction
from time import sleep

from .models import User


def index(request):
    d = {'title': 'EasyBuggy Django'}
    return render(request, 'index.html', d)


def deadlock2(request):
    d = {
        'title': _('title.deadlock2.page'),
        'note': _('msg.note.deadlock2'),
    }
    order = getOrder(request)
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
        str = request.POST["string"]
        if str is not None:
            d['msg'] = str[::-1]

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


# -------- private method
def getOrder(request):
    order = request.GET.get("order")
    if order == 'asc':
        order = 'desc'
    else:
        order = 'asc'
    return order
