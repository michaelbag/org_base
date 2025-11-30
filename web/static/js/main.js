// Основной JavaScript для навигации и поиска

document.addEventListener('DOMContentLoaded', function() {
    const searchForm = document.getElementById('searchForm');
    const organizationSelect = document.getElementById('organization');
    const departmentSelect = document.getElementById('department');
    const resetBtn = document.getElementById('resetBtn');
    const documentsList = document.getElementById('documentsList');
    const resultsCount = document.getElementById('resultsCount');

    // Загрузка отделов при выборе организации
    organizationSelect.addEventListener('change', function() {
        loadDepartments(this.value);
    });

    // Обработка формы поиска
    searchForm.addEventListener('submit', function(e) {
        e.preventDefault();
        searchDocuments();
    });

    // Сброс формы
    resetBtn.addEventListener('click', function() {
        searchForm.reset();
        departmentSelect.innerHTML = '<option value="">Все отделы</option>';
        documentsList.innerHTML = '<p class="empty-state">Выберите критерии поиска и нажмите "Найти"</p>';
        resultsCount.textContent = '';
    });

    // Загрузка отделов
    function loadDepartments(organization) {
        departmentSelect.innerHTML = '<option value="">Загрузка...</option>';
        
        const url = organization 
            ? `/api/departments?organization=${encodeURIComponent(organization)}`
            : '/api/departments';
        
        fetch(url)
            .then(response => response.json())
            .then(departments => {
                departmentSelect.innerHTML = '<option value="">Все отделы</option>';
                departments.forEach(dept => {
                    const option = document.createElement('option');
                    option.value = dept;
                    option.textContent = dept;
                    departmentSelect.appendChild(option);
                });
            })
            .catch(error => {
                console.error('Ошибка загрузки отделов:', error);
                departmentSelect.innerHTML = '<option value="">Ошибка загрузки</option>';
            });
    }

    // Поиск документов
    function searchDocuments() {
        const formData = new FormData(searchForm);
        const params = new URLSearchParams();
        
        for (const [key, value] of formData.entries()) {
            if (value) {
                params.append(key, value);
            }
        }

        documentsList.innerHTML = '<p class="empty-state">Загрузка...</p>';

        fetch(`/api/documents?${params.toString()}`)
            .then(response => response.json())
            .then(documents => {
                displayDocuments(documents);
            })
            .catch(error => {
                console.error('Ошибка поиска:', error);
                documentsList.innerHTML = '<p class="empty-state">Ошибка при загрузке документов</p>';
            });
    }

    // Отображение списка документов
    function displayDocuments(documents) {
        if (documents.length === 0) {
            documentsList.innerHTML = '<p class="empty-state">Документы не найдены</p>';
            resultsCount.textContent = 'Найдено документов: 0';
            return;
        }

        resultsCount.textContent = `Найдено документов: ${documents.length}`;
        
        documentsList.innerHTML = documents.map(doc => {
            const title = doc.title || doc.number || 'Без названия';
            const org = doc.organization || 'Не указана';
            const dept = doc.department || 'Не указан';
            const type = doc.type || 'Не указан';
            const date = doc.date || 'Не указана';
            const status = doc.status || '';
            const statusBadge = status 
                ? `<span class="status-badge status-${status.toLowerCase().replace(/\s+/g, '-')}">${status}</span>`
                : '';

            return `
                <div class="document-card" onclick="window.location.href='/document/${doc.relative_path}'">
                    <h3>${title}</h3>
                    <div class="meta">
                        <span><strong>Организация:</strong> ${org}</span>
                        <span><strong>Отдел:</strong> ${dept}</span>
                        <span><strong>Тип:</strong> ${type}</span>
                        <span><strong>Дата:</strong> ${date}</span>
                        ${status ? `<span>${statusBadge}</span>` : ''}
                    </div>
                </div>
            `;
        }).join('');
    }
});

