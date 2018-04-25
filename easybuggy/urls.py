from django.conf.urls import url
from . import views

app_name = "easybuggy"

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^login/*', views.admins_login, name='admins_login'),
    url(r'^logout/$', views.admins_logout, name='admins_logout'),
    url(r'^admins/*', views.admins, name='admins'),
    url(r'^ping/$', views.ping, name='ping'),
    url(r'^deadlock/$', views.deadlock, name='deadlock'),
    url(r'^deadlock2/$', views.deadlock2, name='deadlock2'),
    url(r'^infiniteloop/$', views.infiniteloop, name='infiniteloop'),
    url(r'^redirectloop/$', views.redirectloop, name='redirectloop'),
    url(r'^memoryleak/$', views.memoryleak, name='memoryleak'),
    url(r'^netsocketleak/$', views.netsocketleak, name='netsocketleak'),
    url(r'^dbconnectionleak/$', views.dbconnectionleak, name='dbconnectionleak'),
    url(r'^filedescriptorleak/$', views.filedescriptorleak, name='filedescriptorleak'),
    url(r'^threadleak/$', views.threadleak, name='threadleak'),
    url(r'^mojibake/$', views.mojibake, name='mojibake'),
    url(r'^iof/$', views.iof, name='iof'),
    url(r'^lotd/$', views.lotd, name='lotd'),
    url(r'^roe/$', views.roe, name='roe'),
    url(r'^te/$', views.te, name='te'),
    url(r'^xss/$', views.xss, name='xss'),
    url(r'^sqlijc/$', views.sqlijc, name='sqlijc'),
    url(r'^commandinjection/$', views.commandinjection, name='commandinjection'),
    url(r'^unrestrictedsizeupload/$', views.unrestrictedsizeupload, name='unrestrictedsizeupload'),
    url(r'^unrestrictedextupload/$', views.unrestrictedextupload, name='unrestrictedextupload'),
    url(r'^verbosemsg/*', views.verbosemsg, name='verbosemsg'),
    url(r'^bruteforce/*', views.bruteforce, name='bruteforce'),
]
