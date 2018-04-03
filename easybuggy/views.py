from django.shortcuts import render, redirect
from django.utils.translation import ugettext as _
from .models import User


def index(request):
    return render(request, 'index.html')


def infiniteloop(request):
    i = 1
    while 0 < i:
        i += 1
    return render(request, 'index.html')


def redirectloop(request):
    return redirect("/redirectloop")


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
        'note': _('msg.note.sqlijc')
    }
    if request.method == 'POST':
        name = request.POST["name"]
        password = request.POST["password"]
        d['users'] = User.objects.raw(
            "SELECT * FROM easybuggy_user WHERE ispublic = 'true' AND name='" + name +
            "' AND password='" + password + "' ORDER BY id")

    return render(request, 'sqlijc.html', d)
