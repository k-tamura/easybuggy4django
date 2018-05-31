 .. image:: https://travis-ci.com/k-tamura/easybuggy4django.svg?branch=master&style=flat
    :target: https://travis-ci.com/k-tamura/easybuggy4django
    :alt: Build status
 
 .. image:: https://img.shields.io/badge/License-MIT-yellow.svg?style=flat
    :target: https://opensource.org/licenses/MIT
    :alt: License

 .. image:: https://img.shields.io/github/release/k-tamura/easybuggy4django.svg?style=flat
    :target: https://github.com/k-tamura/easybuggy4django/releases/latest
    :alt: Latest Version

EasyBuggy Django
================

EasyBuggy Djangoは、Django 2.0で開発されたEasyBuggyのクローンです。
`EasyBuggy <https://github.com/k-tamura/easybuggy>`__ は、メモリリーク、デッドロック、SQLインジェクションなど、バグや脆弱性の動作を理解するためにつくられたバグだらけのWebアプリケーションです。

.. image:: /static/easybuggy.png

クイックスタート
--------------------

::

    $ git clone https://github.com/k-tamura/easybuggy4django.git
    $ cd easybuggy4django/
    $ pip install -r requirements.txt
    $ python manage.py runserver

上記のコマンドを実行する前に、Pythonの仮想環境を構築しておくことをお勧めします:

::

    $ python3 -m venv venv
    $ source venv/bin/activate

以下にアクセス:

::

    http://localhost:8000

停止するには:
^^^^^^^^

:kbd:`CTRL` + :kbd:`C` をクリック

