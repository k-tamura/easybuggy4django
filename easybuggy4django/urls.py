from django.conf.urls import url
from . import views

app_name = "easybuggy4django"

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^template/$', views.hello_template, name='hello_template'),
    url(r'^infiniteloop/$', views.infiniteloop, name='infiniteloop'),
    url(r'^xss/$', views.xss, name='xss'),
]