from django.conf.urls import url
from . import views

app_name = "easybuggy"

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^infiniteloop/$', views.infiniteloop, name='infiniteloop'),
    url(r'^redirectloop/$', views.redirectloop, name='redirectloop'),
    url(r'^roe/$', views.roe, name='roe'),
    url(r'^xss/$', views.xss, name='xss'),
    url(r'^sqlijc/$', views.sqlijc, name='sqlijc'),
]