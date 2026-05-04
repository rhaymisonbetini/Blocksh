from ..domain.favorite import Favorite
from ..infra.storage.favorites_repository import FavoritesRepository


class FavoritesService:
    def __init__(self, repository: FavoritesRepository):
        self._repo = repository

    def add(self, name: str, command_text: str, cwd: str = "") -> Favorite:
        favorite = Favorite(name=name, command_text=command_text, cwd=cwd)
        self._repo.save(favorite)
        return favorite

    def all(self) -> list[Favorite]:
        return self._repo.load_all()

    def remove(self, fav_id: str) -> None:
        self._repo.delete(fav_id)

    def rename(self, fav_id: str, name: str) -> None:
        self._repo.rename(fav_id, name)
