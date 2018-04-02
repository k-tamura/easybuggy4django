from django.conf.urls import url
from . import views

app_name = "easybuggy"

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^infiniteloop/$', views.infiniteloop, name='infiniteloop'),
    url(r'^redirectloop/$', views.redirectloop, name='redirectloop'),
    url(r'^xss/$', views.xss, name='xss'),
]