import os
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()


def verify_credentials(
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
) -> str:
    # Citite la fiecare cerere, nu la import: altfel valoarea ramane inghetata
    # din momentul importului, iar serviciul ar trebui repornit ca sa o schimbe.
    expected_user = os.getenv("RAG_SERVICE_USERNAME")
    expected_password = os.getenv("RAG_SERVICE_PASSWORD")

    if not expected_user or not expected_password:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Autentificarea nu e configurata pe server",
        )

    # compare_digest, nu ==: compararea obisnuita se opreste la primul caracter
    # diferit, iar durata ei lasa parola sa fie ghicita caracter cu caracter.
    # Ambele comparatii se fac inainte de verificare, tot ca sa nu scape un
    # canal lateral: altfel un user gresit ar raspunde mai repede decat unul bun.
    user_ok = secrets.compare_digest(
        credentials.username.encode("utf-8"), expected_user.encode("utf-8")
    )
    password_ok = secrets.compare_digest(
        credentials.password.encode("utf-8"), expected_password.encode("utf-8")
    )

    if not (user_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credentiale invalide",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username
