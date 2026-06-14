import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
creds = Credentials.from_authorized_user_file('mcp_tools/token.json', SCOPES)
servicio = build('calendar', 'v3', credentials=creds)

lista = servicio.calendarList().list().execute()
print('CALENDARIOS DISPONIBLES EN TU CUENTA:')
print('=' * 60)
for cal in lista.get('items', []):
    nombre = cal.get('summary', 'sin nombre')
    id_cal = cal.get('id')
    acceso = cal.get('accessRole')
    primario = cal.get('primary', False)
    print(f"Nombre: {nombre}")
    print(f"  ID: {id_cal}")
    print(f"  Acceso: {acceso}")
    print(f"  Primario: {primario}")
    print('-' * 40)