from django.urls import path

from . import views


app_name = "sales"


urlpatterns = [

    path(
        "report/",
        views.sales_report,
        name="sales_report"
    ),

    path(
        "report/pdf/",
        views.sales_report_pdf,
        name="sales_report_pdf"
    ),

    path(
        "report/excel/",
        views.sales_report_excel,
        name="sales_report_excel"
    ),

]