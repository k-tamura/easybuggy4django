from django.shortcuts import render
from django.http.response import HttpResponse
from datetime import datetime


def index(request):
    return render(request, 'index.html')


def hello_template(request):
    d = {
        'hour': datetime.now().hour,
        'message': 'Sample message',
    }
    return render(request, 'index.html', d)


def infiniteloop(request):
    i = 1
    while 0 < i:
        i += 1
    return render(request, 'index.html')


def xss(request):
    d = {
        'hour': datetime.now().hour,
        'message': 'Sample message',
    }
    return render(request, 'xss.html', d)
