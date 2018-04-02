from django.shortcuts import render, redirect
from django.utils.translation import ugettext as _


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
    str = request.POST["string"]
    if str is not None:
        d = {
            'title': _('title.xss.page'),
            'msg': str[::-1],
        }
    else:
        d = {
            'title': _('title.xss.page'),
            'msg': _('msg.enter.string'),
        }

    return render(request, 'xss.html', d)

