from django.conf.urls import url
from . import views

app_name = "easybuggy"

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^deadlock2/$', views.deadlock2, name='deadlock2'),
    url(r'^infiniteloop/$', views.infiniteloop, name='infiniteloop'),
    url(r'^redirectloop/$', views.redirectloop, name='redirectloop'),
    url(r'^memoryleak/$', views.memoryleak, name='memoryleak'),
    url(r'^iof/$', views.iof, name='iof'),
    url(r'^lotd/$', views.lotd, name='lotd'),
    url(r'^roe/$', views.roe, name='roe'),
    url(r'^te/$', views.te, name='te'),
    url(r'^xss/$', views.xss, name='xss'),
    url(r'^sqlijc/$', views.sqlijc, name='sqlijc'),
    url(r'^commandinjection/$', views.commandinjection, name='commandinjection'),
]
